from typing import Generator

SENTENCE_ENDINGS = [".", "!", "?"]


def stream_llm_response(
    gen, get_text=lambda choice: choice.get("text"), sentence_endings=None
) -> Generator:
    if sentence_endings is None:
        sentence_endings = SENTENCE_ENDINGS
    buffer = ""
    for response in gen:
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


def find_last_punctuation(buffer: str):
    indices = [buffer.rfind(ending) for ending in SENTENCE_ENDINGS]
    return indices and max(indices)


def get_sentence_from_buffer(buffer: str):
    last_punctuation = find_last_punctuation(buffer)
    if last_punctuation:
        return buffer[: last_punctuation + 1], buffer[last_punctuation + 1 :]
    else:
        return None, None
