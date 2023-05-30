from typing import AsyncGenerator, AsyncIterable, Callable, List, Optional

from openai.openai_object import OpenAIObject
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Action, Message, Transcript

SENTENCE_ENDINGS = [".", "!", "?"]


async def stream_openai_response_async(
    gen: AsyncIterable[OpenAIObject],
    get_text: Callable[[dict], str],
    sentence_endings: List[str] = SENTENCE_ENDINGS,
) -> AsyncGenerator:
    buffer = ""
    async for event in gen:
        choices = event.get("choices", [])
        if len(choices) == 0:
            break
        choice = choices[0]
        if choice.finish_reason:
            break
        token = get_text(choice)
        if not token:
            continue
        buffer += token
        if any(token.endswith(ending) for ending in sentence_endings):
            yield buffer.strip()
            buffer = ""
    if buffer.strip():
        yield buffer


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
    chat_messages = (
        [{"role": "system", "content": prompt_preamble}] if prompt_preamble else []
    )
    for event_log in transcript.event_logs:
        if isinstance(event_log, Message):
            chat_messages.append(
                {
                    "role": "assistant" if event_log.sender == Sender.BOT else "user",
                    "content": event_log.text,
                }
            )
        elif isinstance(event_log, Action):
            chat_messages.append(
                {"role": "action_worker", "content": str(event_log.action_output)}
            )
    return chat_messages
