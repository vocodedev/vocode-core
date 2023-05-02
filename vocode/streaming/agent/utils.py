import json
from typing import AsyncGenerator, Callable
from aiohttp_sse_client.client import EventSource

SENTENCE_ENDINGS = [".", "!", "?"]


async def stream_openai_response_async(
    gen: EventSource,
    get_text: Callable[[dict], str],
    sentence_endings: list[str] = SENTENCE_ENDINGS,
) -> AsyncGenerator:
    buffer = ""
    async for event in gen:
        if "[DONE]" in event.data:
            break
        response = json.loads(event.data)
        choices = response.get("choices", [])
        if len(choices) == 0:
            break
        choice = choices[0]
        if choice["finish_reason"]:
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
