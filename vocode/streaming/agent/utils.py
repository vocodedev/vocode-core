from typing import Generator

SENTENCE_ENDINGS = [".", "!", "?"]


def stream_llm_response(
    gen, get_text=lambda choice: choice.get("text"), sentence_endings=SENTENCE_ENDINGS
) -> Generator:
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
