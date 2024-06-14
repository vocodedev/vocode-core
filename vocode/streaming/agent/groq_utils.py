from copy import deepcopy
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from loguru import logger
from groq.types.chat.chat_completion_chunk import ChatCompletionChunk

from vocode.streaming.models.actions import FunctionFragment, PhraseBasedActionTrigger
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    ConferenceEvent,
    EventLog,
    Message,
    Transcript,
)

def vector_db_result_to_groq_chat_message(vector_db_result):
    return {"role": "user", "content": vector_db_result}

def merge_event_logs(event_logs: List[EventLog]) -> List[EventLog]:
    """Returns a new list of event logs where consecutive bot messages are merged."""
    new_event_logs: List[EventLog] = []
    idx = 0
    while idx < len(event_logs):
        bot_messages_buffer: List[Message] = []
        current_log = event_logs[idx]
        while isinstance(current_log, Message) and current_log.sender == Sender.BOT:
            bot_messages_buffer.append(current_log)
            idx += 1
            try:
                current_log = event_logs[idx]
            except IndexError:
                break
        if bot_messages_buffer:
            merged_bot_message = deepcopy(bot_messages_buffer[-1])
            merged_bot_message.text = " ".join(event_log.text for event_log in bot_messages_buffer)
            new_event_logs.append(merged_bot_message)
        else:
            new_event_logs.append(current_log)
            idx += 1

    return new_event_logs

def is_phrase_based_action_event_log(event_log: EventLog) -> bool:
    return (
        (isinstance(event_log, ActionStart) or isinstance(event_log, ActionFinish))
        and event_log.action_input is not None
        and event_log.action_input.action_config is not None
        and isinstance(
            event_log.action_input.action_config.action_trigger, PhraseBasedActionTrigger
        )
    )

def get_groq_chat_messages_from_transcript(
    merged_event_logs: List[EventLog],
    prompt_preamble: str,
) -> List[dict]:
    chat_messages = [{"role": "system", "content": prompt_preamble}]
    for event_log in merged_event_logs:
        if isinstance(event_log, Message):
            if len(event_log.text.strip()) == 0:
                continue
            else:
                chat_messages.append(
                    {
                        "role": ("assistant" if event_log.sender == Sender.BOT else "user"),
                        "content": event_log.to_string(include_sender=False),
                    },
                )
        elif isinstance(event_log, ActionStart):
            action_message: Dict[str, Any]
            if is_phrase_based_action_event_log(event_log=event_log):
                pass
            else:
                action_message = {
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": event_log.action_type,
                        "arguments": event_log.action_input.params.json(),
                    },
                }
                chat_messages.append(action_message)
        elif isinstance(event_log, ActionFinish):
            action_message = {
                "role": "function",
                "name": event_log.action_type,
                "content": event_log.to_string(include_header=False),
            }
            chat_messages.append(action_message)
        elif isinstance(event_log, ConferenceEvent):
            chat_messages.append(
                {"role": "user", "content": event_log.to_string(include_sender=False)},
            )
    return chat_messages

def format_groq_chat_messages_from_transcript(
    transcript: Transcript,
    prompt_preamble: str,
) -> List[dict]:
    # merge consecutive bot messages
    merged_event_logs: List[EventLog] = merge_event_logs(event_logs=transcript.event_logs)

    chat_messages: List[Dict[str, Optional[Any]]]
    chat_messages = get_groq_chat_messages_from_transcript(
        merged_event_logs=merged_event_logs,
        prompt_preamble=prompt_preamble,
    )

    return chat_messages

async def groq_get_tokens(
    gen: AsyncGenerator[ChatCompletionChunk, None],
) -> AsyncGenerator[Union[str, FunctionFragment], None]:
    async for event in gen:
        choices = event.choices
        if len(choices) == 0:
            continue
        choice = choices[0]
        if choice.finish_reason:
            if choice.finish_reason == "content_filter":
                logger.warning(
                    "Detected content filter.",
                    extra={"chat_completion_chunk": event.model_dump()},
                )
            break
        delta = choice.delta
        if delta.content is not None:
            token = delta.content
            yield token
        elif delta.function_call is not None:
            yield FunctionFragment(
                name=(delta.function_call.name if delta.function_call.name is not None else ""),
                arguments=(
                    delta.function_call.arguments
                    if delta.function_call.arguments is not None
                    else ""
                ),
            )