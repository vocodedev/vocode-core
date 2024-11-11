import re
from typing import TypedDict


class MemoryValue(TypedDict):
    is_ephemeral: bool
    value: str


def interpolate_memories(text: str, memories: dict[str, MemoryValue]) -> str:
    result = text
    for key in memories:
        search_pattern = f"[[{key}]]"
        if search_pattern in result:
            memory = memories[key]
            if memory is not None and memory["value"] != "MISSING":
                result = result.replace(search_pattern, memory["value"])
    return result
