from transformers import (
    PreTrainedTokenizerFast,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    AutoTokenizer,
)


from copy import deepcopy
import re
from typing import (
    Dict,
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    List,
    Literal,
    Optional,
    TypeVar,
    Union,
)

from vocode.streaming.models.actions import FunctionCall, FunctionFragment
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    EventLog,
    Message,
    Transcript,
)

SENTENCE_ENDINGS = [".", "!", "?", "\n"]

import requests
import uuid
import json
from vocode import getenv


def translate_message(
    logger, messageString: str, sourceLanguage: str, targetLanguage: str
) -> str:
    key = getenv("AZURE_TRANSLATE_KEY")
    endpoint = "https://api.cognitive.microsofttranslator.com"
    location = "westus3"

    path = "/translate"
    constructed_url = endpoint + path

    params = {"api-version": "3.0", "from": sourceLanguage, "to": [targetLanguage]}

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    body = [{"text": messageString}]
    logger.info(f"Constructed URL: {constructed_url}")
    logger.info(f"Params: {params}")
    logger.info(f"Headers: {headers}")
    logger.info(f"Body: {json.dumps(body)}")
    try:
        request = requests.post(
            constructed_url, params=params, headers=headers, json=body
        )
        response = request.json()
        logger.info(f"Response: {response}")
    except Exception as e:
        logger.error(f"Error in translation: {e}")
        return messageString

    # Assuming the response contains a translation, extract it
    # Note: You might need to handle errors and different response schemas in a real-world scenario
    translated_text = (
        response[0]["translations"][0]["text"] if response else messageString
    )

    return translated_text


async def collate_response_async(
    gen: AsyncIterable[Union[str, FunctionFragment]],
    sentence_endings: List[str] = SENTENCE_ENDINGS,
    get_functions: Literal[True, False] = False,
) -> AsyncGenerator[Union[str, FunctionCall], None]:
    sentence_endings_pattern = "|".join(map(re.escape, sentence_endings))
    list_item_ending_pattern = r"\n"
    buffer = ""
    function_name_buffer = ""
    function_args_buffer = ""
    prev_ends_with_money = False
    async for token in gen:
        if not token:
            continue
        if isinstance(token, str):
            if prev_ends_with_money and token.startswith(" "):
                yield buffer.strip()
                buffer = ""

            buffer += token
            possible_list_item = bool(re.match(r"^\d+[ .]", buffer))
            ends_with_money = bool(re.findall(r"\$\d+.$", buffer))
            if re.findall(
                (
                    list_item_ending_pattern
                    if possible_list_item
                    else sentence_endings_pattern
                ),
                token,
            ):
                # Check if the last word in the buffer is longer than 3 letters
                if not ends_with_money and len(buffer.strip().split(" ")[-1]) >= 4:
                    # also check that the buffer is longer than 2 words
                    # prevents clicking from when the audio plays faster than the next chunk returns
                    # either has a gap in the playback or closes altogether because the chunk is played too quickly
                    if len(buffer.strip().split(" ")) <= 2:
                        continue
                    to_return = buffer.strip()
                    if to_return:
                        yield to_return
                    buffer = ""
            prev_ends_with_money = ends_with_money
        elif isinstance(token, FunctionFragment):
            function_name_buffer += token.name
            function_args_buffer += token.arguments
    to_return = buffer.strip()
    if to_return:
        yield to_return
    if function_name_buffer and get_functions:
        yield FunctionCall(name=function_name_buffer, arguments=function_args_buffer)


async def openai_get_tokens(gen) -> AsyncGenerator[Union[str, FunctionFragment], None]:
    async for event in gen:
        choices = event.choices
        if len(choices) == 0:
            continue
        choice = choices[0]
        if choice.finish_reason:
            break
        delta = choice.delta

        if hasattr(delta, "text") and delta.text:
            token = delta.text
            yield token
        if hasattr(delta, "content") and delta.content:
            token = delta.content
            yield token
        elif hasattr(delta, "function_call") and delta.function_call:
            yield FunctionFragment(
                name=(
                    delta.function_call.name
                    if hasattr(delta.function_call, "name") and delta.function_call.name
                    else ""
                ),
                arguments=(
                    delta.function_call.arguments
                    if hasattr(delta.function_call, "arguments")
                    and delta.function_call.arguments
                    else ""
                ),
            )


def find_last_punctuation(buffer: str) -> Optional[int]:
    indices = [buffer.rfind(ending) for ending in SENTENCE_ENDINGS]
    if not indices:
        return None
    return max(indices)


def get_sentence_from_buffer(buffer: str):
    last_punctuation = find_last_punctuation(buffer)
    if last_punctuation:
        return buffer[: last_punctuation + 1], buffer[last_punctuation + 1 :]
    else:
        return None, None


def format_openai_chat_messages_from_transcript(
    transcript: Transcript, prompt_preamble: Optional[str] = None
) -> List[dict]:
    chat_messages: List[Dict[str, Optional[Any]]] = (
        [{"role": "user", "content": prompt_preamble}] if prompt_preamble else []
    )

    # merge consecutive bot messages
    new_event_logs: List[EventLog] = []
    idx = 0
    while idx < len(transcript.event_logs):
        bot_messages_buffer: List[Message] = []
        current_log = transcript.event_logs[idx]
        while isinstance(current_log, Message) and current_log.sender == Sender.BOT:
            bot_messages_buffer.append(current_log)
            idx += 1
            try:
                current_log = transcript.event_logs[idx]
            except IndexError:
                break
        if bot_messages_buffer:
            merged_bot_message = deepcopy(bot_messages_buffer[-1])
            merged_bot_message.text = " ".join(
                event_log.text for event_log in bot_messages_buffer
            )
            new_event_logs.append(merged_bot_message)
        else:
            new_event_logs.append(current_log)
            idx += 1

    for event_log in new_event_logs:
        if isinstance(event_log, Message):
            chat_messages.append(
                {
                    "role": "assistant" if event_log.sender == Sender.BOT else "user",
                    "content": event_log.text,
                }
            )
        elif isinstance(event_log, ActionStart):
            chat_messages.append(
                {
                    "role": "user",
                    "content": None,
                    "function_call": {
                        "name": event_log.action_type,
                        "arguments": f"SYSTEM: Submitted: Function call: {event_log.action_type} with arguments {event_log.action_input.params.json()}\nDo not answer the user's associated query until a response is received from the system.<|im_end|>\n",
                    },
                }
            )
        elif isinstance(event_log, ActionFinish):
            chat_messages.append(
                {
                    "role": "user",
                    "name": event_log.action_type,
                    "content": f"SYSTEM: Completed: Function {event_log.action_type}.\nResponse was: {event_log.action_output.response.json()}\nNow you can use the response in the conversation.<|im_end|>\n",
                }
            )
    return chat_messages


def format_tool_completion_from_transcript(
    transcript: Transcript,
    latest_agent_response: str,
) -> List[str]:
    messages_content = []

    # merge consecutive bot messages
    new_event_logs: List[EventLog] = []
    idx = 0
    while idx < len(transcript.event_logs):
        bot_messages_buffer: List[Message] = []
        current_log = transcript.event_logs[idx]
        while isinstance(current_log, Message) and current_log.sender == Sender.BOT:
            bot_messages_buffer.append(current_log)
            idx += 1
            try:
                current_log = transcript.event_logs[idx]
            except IndexError:
                break

        if bot_messages_buffer:
            merged_bot_message = deepcopy(bot_messages_buffer[-1])
            merged_bot_message.text = " ".join(
                event_log.text
                for event_log in bot_messages_buffer
                if event_log.text.strip()
            )
            if merged_bot_message.text.strip():
                new_event_logs.append(merged_bot_message)
        else:
            if (
                isinstance(current_log, Message) and current_log.text.strip()
            ) or isinstance(current_log, (ActionStart, ActionFinish)):
                new_event_logs.append(current_log)
            idx += 1

    for event_log in new_event_logs:
        if isinstance(event_log, Message) and event_log.text.strip():
            messages_content.append(event_log.text)
    messages_content.append(latest_agent_response)
    return messages_content


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


def format_openai_chat_completion_from_transcript(
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

    current_doc = {"title": "", "text": ""}
    added_current_doc = False
    # Convert event logs to messages format, including ActionStart and ActionFinish
    for event_log in transcript.event_logs:
        if len(current_doc["title"]) > 0 and len(current_doc["text"]) > 0:
            messages.append({"role": "system", "content": render_docs([current_doc])})
            current_doc = {"title": "", "text": ""}
            added_current_doc = True
        if isinstance(event_log, Message) and event_log.text.strip():
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            messages.append({"role": role, "content": event_log.text})
        elif isinstance(event_log, ActionStart):
            current_doc["title"] = (
                event_log.action_type + " " + event_log.action_input.params.json()
            )
            added_current_doc = False
        elif isinstance(event_log, ActionFinish):
            current_doc["text"] = event_log.action_output.response.json()
    if not added_current_doc and (
        len(current_doc["title"]) > 0 or len(current_doc["text"]) > 0
    ):
        messages.append(
            {
                "role": "system",
                "content": render_docs([current_doc])
                + f"\n\n{event_log.action_type} submitted. Do not provide a response yet. You may inform the user that the action is being run. Please wait for the response.",
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
    except Exception as e:
        raise e

    return input_ids, merged_messages


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
        # add a blank user message
        messages.append({"role": "user", "content": "Begin."})
    current_doc = {"title": "", "text": ""}
    added_current_doc = False
    # Convert event logs to messages format, including ActionStart and ActionFinish
    for event_log in events:
        if len(current_doc["title"]) > 0 and len(current_doc["text"]) > 0:
            messages.append({"role": "system", "content": render_docs([current_doc])})
            current_doc = {"title": "", "text": ""}
            added_current_doc = True
        if isinstance(event_log, Message) and event_log.text.strip():
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            messages.append({"role": role, "content": event_log.text})
        elif isinstance(event_log, ActionStart):
            current_doc["title"] = (
                event_log.action_type + " " + event_log.action_input.params.json()
            )
        elif isinstance(event_log, ActionFinish):
            current_doc["text"] = event_log.action_output.response.json()
    if not added_current_doc and len(current_doc["text"]) > 0:
        messages.append(
            {
                "role": "system",
                "content": render_docs([current_doc])
                + "\nAction is being run. Please wait for the response.",
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


def vector_db_result_to_openai_chat_message(vector_db_result):
    return {"role": "user", "content": vector_db_result}
