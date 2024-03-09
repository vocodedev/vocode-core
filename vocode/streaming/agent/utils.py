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
                if not ends_with_money and len(buffer.strip().split()[-1]) >= 4:
                    # also check that the buffer is longer than 2 words
                    # prevents clicking from when the audio plays faster than the next chunk returns
                    # either has a gap in the playback or closes altogether because the chunk is played too quickly
                    if len(buffer.strip().split()) <= 2:
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
        [{"role": "system", "content": prompt_preamble}] if prompt_preamble else []
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


def format_openai_chat_completion_from_transcript(
    transcript: Transcript, prompt_preamble: Optional[str] = None
) -> str:
    formatted_conversation = ""
    if prompt_preamble:
        formatted_conversation += f"<|im_start|>system\n{prompt_preamble}<|im_end|>\n"

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
        if isinstance(event_log, Message):
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            if event_log.text.strip():
                formatted_conversation += (
                    f"<|im_start|>{role}\n{event_log.text}<|im_end|>\n"
                )
        elif isinstance(event_log, ActionStart):
            formatted_conversation += f"<|im_start|>user\nSYSTEM: Submitted: Function call: {event_log.action_type} with arguments {event_log.action_input.params.json()}\nDo not answer the user's associated query until a response is received from the system.<|im_end|>\n"
        elif isinstance(event_log, ActionFinish):
            formatted_conversation += f"<|im_start|>user\nSYSTEM: Completed: Function {event_log.action_type}.\nResponse was: {event_log.action_output.response.json()}\nNow you can use the response in the conversation.<|im_end|>\n"

    return formatted_conversation.strip()


def vector_db_result_to_openai_chat_message(vector_db_result):
    return {"role": "user", "content": vector_db_result}
