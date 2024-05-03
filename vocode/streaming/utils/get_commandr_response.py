from copy import deepcopy
import json
from logging import Logger
from typing import Any, Dict, List, Optional
import aiohttp
from vocode import getenv
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    EventLog,
    Message,
    Transcript,
)
from transformers import (
    PreTrainedTokenizerFast,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    AutoTokenizer,
)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer 'EMPTY'",
}


def render_docs(docs: list[dict]) -> str:
    """Render a list of doc dicts to a single formatted string."""
    doc_str_list = ["<results>"]
    for doc_idx, doc in enumerate(docs):
        if doc_idx > 0:
            doc_str_list.append("")
        doc_str_list.extend([f"Document: {str(doc_idx)}", doc["title"], doc["text"]])
    doc_str_list.append("</results>")
    return "\n".join(doc_str_list)


def render_chat_history(_conversation: list[dict]) -> str:
    chat_hist_str = ""
    for turn in _conversation:
        chat_hist_str += "<|START_OF_TURN_TOKEN|>"
        if turn["role"] == "user":
            chat_hist_str += "<|USER_TOKEN|>"
        elif turn["role"] == "assistant":
            chat_hist_str += "<|CHATBOT_TOKEN|>"
        else:  # role == system
            chat_hist_str += "<|SYSTEM_TOKEN|>"
        chat_hist_str += turn["content"]
        chat_hist_str += "<|END_OF_TURN_TOKEN|>"
    return chat_hist_str


def format_prefix_completion_from_transcript(events: List[EventLog]):
    EOS_TOKEN = "</s>"

    # get an array of just the message contents within each event log
    messages = [
        event_log.text for event_log in events if isinstance(event_log, Message)
    ]
    last_three = messages[-3:]
    prompt = "\n".join(last_three)
    alpaca_prompt = f"""### Prompt:\n{prompt}\n\n### Completion:\n"""
    return alpaca_prompt


def format_command_function_completion_from_transcript(
    tokenizer: AutoTokenizer,
    events: List[EventLog],
    tools: List[Dict[str, Any]],
    prompt_preamble: Optional[str] = None,
) -> str:
    # Initialize the messages list
    messages = []
    # Add the prompt preamble if it exists
    if prompt_preamble:
        messages.append({"role": "system", "content": prompt_preamble})
    current_doc = {"action_type": "", "action_input": "", "action_output": ""}
    # Convert event logs to messages format, including ActionStart and ActionFinish
    for event_log in events:
        if (
            len(current_doc["action_type"]) > 0
            and len(current_doc["action_output"]) > 0
            and len(current_doc["action_input"]) > 0
        ):
            messages.append(
                {
                    "role": "system",
                    "content": f"Action: ```json\n{{\n    \"tool_name\": \"{current_doc['action_type']}\",\n    \"parameters\": {current_doc['action_input']},\n    \"tool_output\": {current_doc['action_output']}\n}}\n```",
                }
            )
            current_doc = {"action_type": "", "action_input": "", "action_output": ""}
        if isinstance(event_log, Message) and event_log.text.strip():
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            messages.append({"role": role, "content": event_log.text})
        elif isinstance(event_log, ActionStart):
            current_doc["action_type"] = event_log.action_type
            current_doc["action_input"] = event_log.action_input.params.json()
        elif isinstance(event_log, ActionFinish):
            current_doc["action_output"] = event_log.action_output.response.json()
    # if there is action type and action input, put it in the messages
    if len(current_doc["action_type"]) > 0 and len(current_doc["action_input"]) > 0:
        messages.append(
            {
                "role": "system",
                "content": f"Action: ```json\n{{\n    \"tool_name\": \"{current_doc['action_type']}\",\n    \"parameters\": {current_doc['action_input']}\n}}\n\nThe above action is being run. Please wait for the response.```",
            }
        )
        # wrap the last user message in a text that says a tool is being run
        # we do this to avoid hallucinations during the phase when the tool is pending
        for i in range(len(messages) - 1, -1, -1):
            if (
                messages[i]["role"] == "user"
                and len(str(messages[i]["content"]).strip()) > 0
            ):
                messages[i]["content"] = (
                    messages[i]["content"]
                    + f"\n\nRemember: The action {current_doc['action_type']} is still being run. Please wait for the response."
                )
                break
    # Merge consecutive messages from the same sender
    merged_messages = []
    idx = 0
    while idx < len(messages):
        current_message = messages[idx]
        message_buffer = [current_message["content"]]
        idx += 1
        while idx < len(messages) and messages[idx]["role"] == current_message["role"]:
            message_buffer.append(messages[idx]["content"])
            idx += 1

        merged_content = " ".join(message_buffer)
        merged_messages.append(
            {"role": current_message["role"], "content": merged_content}
        )

    # Use the tokenizer to convert merged messages to text
    input_ids = tokenizer.apply_tool_use_template(
        merged_messages,
        tools=tools,
        tokenize=False,
        add_generation_prompt=True,
    )
    input_ids = input_ids.replace("directly_answer", "answer")
    input_ids = input_ids.replace("directly-answer", "answer")
    to_replace = "You are a powerful conversational AI trained by Cohere to help people. You are augmented by a number of tools, and your job is to use and consume the output of these tools to best help the user. You will see a conversation history between yourself and a user, ending with an utterance from the user. You will then see a specific instruction instructing you what kind of response to generate. When you answer the user's requests, you cite your sources in your answers, according to those instructions."
    replace_with = "You are a capable telephone AI. You have been developed and trained by a company called OpenCall to help people over the phone. You are augmented by a number of tools, and your job is to converse with the user, while simultaneously using and consuming these tools only when your instructions indicate to do so. You will see a conversation history between yourself and a user, either ending with an utterance from the user or an indication from the system regarding the status of any tools being run."
    input_ids = input_ids.replace(to_replace, replace_with)

    to_replace = "## Available Tools"
    replace_with = """## Style Guide
To respond to the user or consume the output of a tool, you must use the answer tool. Only use tools as instructed and do not use tools again if the system indicates that the tool has completed.

## Available Tools"""
    input_ids = input_ids.replace(to_replace, replace_with)

    # to_replace = "You can use any of the supplied tools any number of times, but you should aim to execute the minimum number of necessary actions for the input."
    # replace_with = "Critically, you may only use a single tool per turn. As such, the json formatted list of actions you return should only contain a single action."
    # input_ids = input_ids.replace(to_replace, replace_with)

    # to_replace = "of actions that you want to perform"
    # replace_with = "containing a single action that you want to perform"
    # input_ids = input_ids.replace(to_replace, replace_with)

    return input_ids, merged_messages


def format_command_grounded_completion_from_transcript(
    tokenizer: AutoTokenizer,
    events: List[EventLog],
    documents: List[dict],
    prompt_preamble: Optional[str] = None,
) -> str:
    # Initialize the messages list
    messages = []
    # Add the prompt preamble if it exists
    if prompt_preamble:
        messages.append({"role": "system", "content": prompt_preamble})
        # add a blank user message
        messages.append({"role": "user", "content": "Begin."})
    current_doc = {"title": "", "text": ""}
    # Convert event logs to messages format, including ActionStart and ActionFinish
    for event_log in events:
        if len(current_doc["title"]) > 0 and len(current_doc["text"]) > 0:
            messages.append({"role": "system", "content": render_docs(current_doc)})
            current_doc = {"title": "", "text": ""}
        if isinstance(event_log, Message) and event_log.text.strip():
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            messages.append({"role": role, "content": event_log.text})
        elif isinstance(event_log, ActionStart):
            current_doc["title"] = (
                event_log.action_type + " " + event_log.action_input.params.json()
            )
        elif isinstance(event_log, ActionFinish):
            current_doc["text"] = event_log.action_output.response.json()

    # Merge consecutive messages from the same sender
    merged_messages = []
    idx = 0
    while idx < len(messages):
        current_message = messages[idx]
        message_buffer = [current_message["content"]]
        idx += 1
        while idx < len(messages) and messages[idx]["role"] == current_message["role"]:
            message_buffer.append(messages[idx]["content"])
            idx += 1

        merged_content = " ".join(message_buffer)
        merged_messages.append(
            {"role": current_message["role"], "content": merged_content}
        )

    # Use the tokenizer to convert merged messages to text
    # Use the tokenizer to convert merged messages to text
    input_ids = (
        render_chat_history(merged_messages)
        + "<|END_OF_TURN_TOKEN|>"
        + "<|START_OF_TURN_TOKEN|>"
        + "<|CHATBOT_TOKEN|>"
    ).replace("<|END_OF_TURN_TOKEN|><|END_OF_TURN_TOKEN|>", "<|END_OF_TURN_TOKEN|>")

    return input_ids, merged_messages


def format_commandr_chat_completion_from_transcript(
    transcript: Transcript,
    prompt_preamble: Optional[str] = None,
) -> str:
    # Initialize the messages list
    messages = []
    # Add the prompt preamble if it exists
    if prompt_preamble:
        messages.append({"role": "system", "content": prompt_preamble})
        # # add a blank user message
        # messages.append({"role": "user", "content": "Begin."})

    current_doc = {"action_type": "", "action_input": "", "action_output": ""}
    # Convert event logs to messages format, including ActionStart and ActionFinish
    events = transcript.event_logs
    for event_log in events:
        if (
            len(current_doc["action_type"]) > 0
            and len(current_doc["action_output"]) > 0
            and len(current_doc["action_input"]) > 0
        ):
            messages.append(
                {
                    "role": "system",
                    "content": f"Action Completed: ```json\n{{\n    \"tool_name\": \"{current_doc['action_type']}\",\n    \"parameters\": {current_doc['action_input']},\n    \"tool_output\": {current_doc['action_output']}\n}}\n\nYou may directly respond to the user.```",
                }
            )
            current_doc = {"action_type": "", "action_input": "", "action_output": ""}
        if isinstance(event_log, Message) and event_log.text.strip():
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            messages.append({"role": role, "content": event_log.text})
        elif isinstance(event_log, ActionStart):
            current_doc["action_type"] = event_log.action_type
            current_doc["action_input"] = event_log.action_input.params.json()
        elif isinstance(event_log, ActionFinish):
            current_doc["action_output"] = event_log.action_output.response.json()
    # if there is action type and action input, put it in the messages
    if len(current_doc["action_type"]) > 0 and len(current_doc["action_input"]) > 0:
        messages.append(
            {
                "role": "system",
                "content": f"Action Pending: ```json\n{{\n    \"tool_name\": \"{current_doc['action_type']}\",\n    \"parameters\": {current_doc['action_input']}\n}}\n\nYou do not have the result. Yet, you may directly respond to the user.```",
            }
        )
    # Merge consecutive messages from the same sender
    merged_messages = []
    idx = 0
    while idx < len(messages):
        current_message = messages[idx]
        message_buffer = [current_message["content"]]
        idx += 1
        while idx < len(messages) and messages[idx]["role"] == current_message["role"]:
            message_buffer.append(messages[idx]["content"])
            idx += 1

        merged_content = " ".join(message_buffer)
        merged_messages.append(
            {"role": current_message["role"], "content": merged_content}
        )

    try:
        # Use the tokenizer to convert merged messages to text
        input_ids = render_chat_history(merged_messages)
        input_ids += "<|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>"
        input_ids = input_ids.replace("directly_answer", "answer")
        input_ids = input_ids.replace("directly-answer", "answer")
    except Exception as e:
        raise e
    return input_ids, merged_messages


async def get_commandr_response(prompt_buffer: str, model: str, logger: Logger):
    response_text = ""
    prompt_buffer = prompt_buffer.replace("directly_answer", "answer")
    prompt_buffer = prompt_buffer.replace("directly-answer", "answer")
    async with aiohttp.ClientSession() as session:
        # log the model
        logger.info(f"Model: {model}")
        # TODO: Change at some point, this is bc haproxy can't do ngrok
        if "medusa" in model.lower():
            base_url = getenv("AI_API_HUGE_BASE")
            model = getenv("AI_MODEL_NAME_HUGE")
        else:
            base_url = getenv("AI_API_BASE")
            model = getenv("AI_MODEL_NAME_LARGE")
        data = {
            "model": model,
            "prompt": prompt_buffer,
            "stream": False,
            "stop": ["<|END_OF_TURN_TOKEN|>"],
            "max_tokens": 250,
            "top_p": 0.9,
            "temperature": 0.1,
            "include_stop_str_in_output": False,
        }

        async with session.post(
            f"{base_url}/completions", headers=HEADERS, json=data
        ) as response:
            if response.status == 200:
                response_data = await response.json()
                if "choices" in response_data and response_data["choices"]:
                    response_text = (
                        response_data["choices"][0]
                        .get("text", "")
                        .replace("SYSTEM", "")
                    )
            else:
                logger.error(
                    f"Error while getting response from tool check: {str(response)}"
                )
    # remove end of turn
    response_text = response_text.replace("<|END_OF_TURN_TOKEN|>", "")
    return response_text


async def get_commandr_response_streaming(
    prompt_buffer: str, model: str, logger: Logger
):
    prompt_buffer = prompt_buffer.replace("directly_answer", "answer")
    prompt_buffer = prompt_buffer.replace("directly-answer", "answer")
    to_add = '''Action: ```json
[
      {
          "tool_name": "'''
    prompt_buffer += to_add
    # log the prompt buffer
    async with aiohttp.ClientSession() as session:
        # TODO: Change at some point, this is bc haproxy can't do ngrok
        if "medusa" in model.lower():
            base_url = getenv("AI_API_HUGE_BASE")
            model = getenv("AI_MODEL_NAME_HUGE")
        else:
            base_url = getenv("AI_API_BASE")
            model = getenv("AI_MODEL_NAME_LARGE")
        data = {
            "model": model,
            "prompt": prompt_buffer,
            "stream": True,  # Changed to True to make it stream the output
            "stop": ["<|END_OF_TURN_TOKEN|>"],
            "max_tokens": 250,
            "top_p": 0.9,
            "temperature": 0.1,
            "include_stop_str_in_output": False,
        }
        async with session.post(
            f"{base_url}/completions", headers=HEADERS, json=data
        ) as response:
            # first yield out the prefix
            yield to_add
            # Since we are streaming, we need to process the response as it arrives
            async for chunk in response.content:
                if chunk == b"\n":
                    continue
                chunk = chunk.decode("utf-8")
                if chunk.startswith("data:"):
                    # Decode payload
                    try:
                        json_payload = json.loads(chunk.lstrip("data:").rstrip("/n"))
                        text = json_payload.get("choices", "")[0].get("text", "")
                        yield text.replace("SYSTEM", "").replace(
                            "<|END_OF_TURN_TOKEN|>", ""
                        )
                    except Exception as e:
                        logger.error(
                            f"Error while processing response. Error was: {str(e)} and the response was: {chunk}"
                        )


async def get_commandr_response_chat_streaming(
    transcript: Transcript, model: str, prompt_preamble: str, logger: Logger
):
    prompt_buffer, messages = format_commandr_chat_completion_from_transcript(
        prompt_preamble=prompt_preamble,
        transcript=transcript,
    )
    # TODO: Change at some point, this is bc haproxy can't do ngrok
    if "medusa" in model.lower():
        base_url = getenv("AI_API_HUGE_BASE")
        model = getenv("AI_MODEL_NAME_HUGE")
    else:
        base_url = getenv("AI_API_BASE")
        model = getenv("AI_MODEL_NAME_LARGE")
    async with aiohttp.ClientSession() as session:
        base_url = base_url
        data = {
            "model": model,
            "prompt": prompt_buffer,
            "stream": True,
            "stop": ["<|END_OF_TURN_TOKEN|>"],
            "max_tokens": 250,
            "top_p": 0.9,
            "include_stop_str_in_output": False,
            "temperature": 0.1,
        }

        async with session.post(
            f"{base_url}/completions", headers=HEADERS, json=data
        ) as response:
            async for chunk in response.content:
                if chunk == b"\n":
                    continue
                chunk = chunk.decode("utf-8")
                if chunk.startswith("data:"):
                    try:
                        json_payload = json.loads(chunk.lstrip("data:").rstrip("/n"))
                        text = json_payload.get("choices", "")[0].get("text", "")
                        yield text.replace("SYSTEM", "").replace(
                            "<|END_OF_TURN_TOKEN|>", ""
                        )
                    except Exception as e:
                        logger.error(f"Error while processing response: {str(e)}")
