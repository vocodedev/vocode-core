from copy import deepcopy
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
    input_ids = input_ids.replace("directly_answer", "send-direct-response")
    input_ids = input_ids.replace("directly-answer", "send-direct-response")

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
    tokenizer: AutoTokenizer,
    transcript: Transcript,
    prompt_preamble: Optional[str] = None,
    did_action: str = None,
    reason: str = "",
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
                "content": f"Action: ```json\n{{\n    \"tool_name\": \"{current_doc['action_type']}\",\n    \"parameters\": {current_doc['action_input']}\n}}\n```",
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
        # if not did_action:
        #     input_ids += "<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>Agent did not perform an action.<|END_OF_TURN_TOKEN|>"
        # if not did_action:
        #     input_ids += f"<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>Agent performed an action: {did_action}<|END_OF_TURN_TOKEN|>"
        if len(reason) > 0:
            input_ids += f"<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>No action taken because: {reason}<|END_OF_TURN_TOKEN|>"
        input_ids += "<|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>"
        input_ids = input_ids.replace("directly_answer", "send-direct-response")
        input_ids = input_ids.replace("directly-answer", "send-direct-response")
    except Exception as e:
        raise e

    return input_ids, merged_messages


async def get_commandr_response(prompt_buffer: str, logger: Logger):
    response_text = ""
    prompt_buffer = prompt_buffer.replace("directly_answer", "send-direct-response")
    prompt_buffer = prompt_buffer.replace("directly-answer", "send-direct-response")
    async with aiohttp.ClientSession() as session:
        base_url = getenv("AI_API_BASE")
        data = {
            "model": getenv("AI_MODEL_NAME_LARGE"),
            "prompt": prompt_buffer,
            "stream": False,
            "stop": ["<|END_OF_TURN_TOKEN|>"],
            "max_tokens": 500,
            "include_stop_str_in_output": True,
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
