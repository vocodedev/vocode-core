import re
from vocode.streaming.agent.state_agent import MemoryValue


def interpolate_memories(text: str, memories: dict[str, MemoryValue]) -> str:
    def get_memory_value(match: re.Match):
        key = match.group(1)
        default_value = match.group(0)
        memory = memories.get(key)
        if memory == None:
            return default_value
        memory_value = memory["value"]
        return memory_value if memory_value != "MISSING" else default_value
    return re.sub(r"\[\[(\w+)\]\]", get_memory_value, text)