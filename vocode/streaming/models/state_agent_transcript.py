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
    BRANCH_DECISION = "branch_decision"
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
    message_sent: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

    class Config:
        use_enum_values = True


class StateAgentTranscriptDebugEntry(StateAgentTranscriptEntry):
    role: StateAgentTranscriptRole = StateAgentTranscriptRole.DEBUG
    type: StateAgentDebugMessageType


class StateAgentTranscriptActionFinish(StateAgentTranscriptEntry):
    role: StateAgentTranscriptRole = StateAgentTranscriptRole.ACTION_FINISH
    action_name: str
    runtime_inputs: dict


class StateAgentTranscriptActionInvoke(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.ACTION_INOKE
    message: str = "action invoked"
    state_id: str
    action_name: str


class StateAgentTranscriptBranchDecision(StateAgentTranscriptDebugEntry):
    type: StateAgentDebugMessageType = StateAgentDebugMessageType.BRANCH_DECISION
    message: str = "branch decision"
    ai_prompt: str
    ai_tool: dict[str, str]
    ai_response: str
    internal_edges: List[dict]
    original_state: dict


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
    original_state: Optional[dict] = None
    extra_info: Optional[dict] = None


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
                if entry["role"] == StateAgentTranscriptRole.ACTION_FINISH:
                    parsed_entries.append(StateAgentTranscriptActionFinish(**entry))
                elif "type" in entry:
                    if entry["type"] == StateAgentDebugMessageType.ACTION_INOKE:
                        parsed_entries.append(StateAgentTranscriptActionInvoke(**entry))
                    elif entry["type"] == StateAgentDebugMessageType.ACTION_ERROR:
                        parsed_entries.append(StateAgentTranscriptActionError(**entry))
                    elif entry["type"] == StateAgentDebugMessageType.HANDLE_STATE:
                        parsed_entries.append(StateAgentTranscriptHandleState(**entry))
                    elif entry["type"] == StateAgentDebugMessageType.BRANCH_DECISION:
                        parsed_entries.append(
                            StateAgentTranscriptBranchDecision(**entry)
                        )
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
