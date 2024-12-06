import re
from typing import List, Optional

_GOODBYE_PHRASES = [
    "bye",
]


def is_goodbye_simple(message: str, phrases: Optional[List[str]]):
    if not phrases:
        phrases = _GOODBYE_PHRASES
    cleaned = re.sub(r"[^\w\s]", "", message.lower())
    return any(phrase in cleaned for phrase in phrases)
