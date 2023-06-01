import re
from typing import AsyncGenerator, AsyncIterable, Callable, List, Optional

from openai.openai_object import OpenAIObject
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Action, Message, Transcript

SENTENCE_ENDINGS = [".", "!", "?", "\n"]


def _sent_tokenize(text: str, sentence_endings: List[str]) -> List[str]:
    sentence_endings = [e for e in sentence_endings if e != "."]
    sentence_endings_pattern = "|".join(map(re.escape, sentence_endings))

    # Replace sentence endings with a unique marker
    text = re.sub(f"([{sentence_endings_pattern}])", r"\1<END>", text)

    sentences = text.split("<END>")

    # Additional logic to handle numbered list items
    combined_sentences = []
    buffer = ""
    for sentence in sentences:
        # If the sentence starts with a number and a space, it's part of a list
        if re.match(r"^\d+ ", sentence):
            buffer += sentence + " "
        else:
            if buffer:
                # Add the current buffer to combined_sentences and start a new buffer
                combined_sentences.append(buffer.strip())
                buffer = ""
            combined_sentences.append(sentence)
    if buffer:
        combined_sentences.append(buffer.strip())

    return combined_sentences


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

        sentences = _sent_tokenize(buffer, sentence_endings)
        for sentence in sentences[:-1]:
            if sentence.strip():
                yield sentence.strip()
        buffer = sentences[-1]
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
