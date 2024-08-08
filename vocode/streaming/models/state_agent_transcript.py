from enum import Enum
from typing import Any, Dict, List, TypedDict
from pydantic import BaseModel, Field
import datetime


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


class StateAgentTranscriptDebugEntry(StateAgentTranscriptEntry):
    role: StateAgentTranscriptRole = StateAgentTranscriptRole.DEBUG
    type: StateAgentDebugMessageType  # action_invoke, action_error, handle_state, or invariant_violation

    class Config:
        use_enum_values = True


class StateAgentTranscriptActionInvoke(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = "action_invoke"
    message: str = "action invoked"
    state_id: str
    action_name: str

    class Config:
        use_enum_values = True


class StateAgentTranscriptActionError(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.ACTION_ERROR
    action_name: str
    raw_error_message: str

    class Config:
        use_enum_values = True


class StateAgentTranscriptHandleState(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.HANDLE_STATE
    message: str = ""
    state_id: str

    class Config:
        use_enum_values = True


class StateAgentTranscriptInvariantViolation(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.INVARIANT_VIOLATION

    class Config:
        use_enum_values = True


class StateAgentTranscript(JsonTranscript):
    version: str = "StateAgent_v0"
    entries: List[StateAgentTranscriptEntry] = []

    class Config:
        use_enum_values = True
