import datetime
import json
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field, root_validator

from vocode.streaming.models.memory_dependency import MemoryDependency


class StateAgentTranscriptRole(str, Enum):
    BOT = "message.bot"
    HUMAN = "human"
    ACTION_FINISH = "action-finish"
    DEBUG = "debug"


class StateAgentDebugMessageType(str, Enum):
    ACTION_INOKE = "action_invoke"
    ACTION_ERROR = "action_error"
    HANDLE_STATE = "handle_state"
    # for errors that indicate a bug in our code
    INVARIANT_VIOLATION = "invariant_violation"


class JsonTranscript(BaseModel):
    version: str

    class Config:
        use_enum_values = True


class StateAgentTranscriptEntry(BaseModel):
    role: StateAgentTranscriptRole
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

    class Config:
        use_enum_values = True


class StateAgentTranscriptMessage(StateAgentTranscriptEntry):
    role: StateAgentTranscriptRole
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

    class Config:
        use_enum_values = True


class StateAgentTranscriptDebugEntry(StateAgentTranscriptEntry):
    role: StateAgentTranscriptRole = StateAgentTranscriptRole.DEBUG
    type: StateAgentDebugMessageType


class StateAgentTranscriptActionInvoke(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.ACTION_INOKE
    message: str = "action invoked"
    state_id: str
    action_name: str


class StateAgentTranscriptActionError(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.ACTION_ERROR
    action_name: str
    raw_error_message: str


class StateAgentTranscriptHandleState(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.HANDLE_STATE
    message: str = ""
    state_id: str
    generated_label: str
    memory_dependencies: Optional[List[MemoryDependency]]
    memory_values: dict


class StateAgentTranscriptInvariantViolation(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.INVARIANT_VIOLATION


TranscriptEntryType = Union[
    StateAgentTranscriptEntry,
    StateAgentTranscriptActionInvoke,
    StateAgentTranscriptActionError,
    StateAgentTranscriptHandleState,
    StateAgentTranscriptInvariantViolation,
]


class StateAgentTranscript(JsonTranscript):
    version: str = "StateAgent_v0"
    entries: List[TranscriptEntryType] = []

    @root_validator(pre=True)
    def parse_entries(cls, values):
        if "entries" in values:
            parsed_entries = []
            for entry in values["entries"]:
                if "type" in entry:
                    if entry["type"] == StateAgentDebugMessageType.ACTION_INOKE:
                        parsed_entries.append(StateAgentTranscriptActionInvoke(**entry))
                    elif entry["type"] == StateAgentDebugMessageType.ACTION_ERROR:
                        parsed_entries.append(StateAgentTranscriptActionError(**entry))
                    elif entry["type"] == StateAgentDebugMessageType.HANDLE_STATE:
                        parsed_entries.append(StateAgentTranscriptHandleState(**entry))
                    elif (
                        entry["type"] == StateAgentDebugMessageType.INVARIANT_VIOLATION
                    ):
                        parsed_entries.append(
                            StateAgentTranscriptInvariantViolation(**entry)
                        )
                else:
                    parsed_entries.append(StateAgentTranscriptMessage(**entry))
            values["entries"] = parsed_entries
        return values

    class Config:
        use_enum_values = True
