from typing import Any, Dict, List, TypedDict
from pydantic import BaseModel, Field
import datetime

class JsonTranscript(BaseModel):
   version: str

class StateAgentTranscriptEntry(BaseModel):
   role: str
   message: str
   timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

class StateAgentTranscript(JsonTranscript):
   version: str = "StateAgent_v0"
   entries: List[StateAgentTranscriptEntry] = []