from typing import Optional
from pydantic import BaseModel


class MemoryDependency(BaseModel):
    key: str
    question: dict  # {type: 'verbatim', message: str} | {type: 'description', description: str}
    description: Optional[str]
    is_ephemeral: Optional[bool]
