from transformers import PreTrainedTokenizerFast
import asyncio
from enum import Enum
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel
from vocode.streaming.models.model import TypedModel
from vocode.streaming.models.events import ActionEvent, Sender, Event, EventType
from pydantic import BaseModel, Field
import time


class ActionType(str, Enum):
    BASE = "action_base"
    NYLAS_SEND_EMAIL = "nylas_send_email"
    TRANSFER_CALL = "transfer_call"
    HANGUP_CALL = "hangup_call"
    SEARCH_ONLINE = "search_online"
    SEND_TEXT = "send_text"
    SEND_EMAIL = "send_email"


class ActionConfig(TypedModel, type=ActionType.BASE):
    pass


class EventLog(BaseModel):
    sender: Sender
    timestamp: float = Field(default_factory=time.time)

    def to_string(self, include_timestamp: bool = False) -> str:
        raise NotImplementedError


class Message(EventLog):
    text: str

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


ParametersType = TypeVar("ParametersType", bound=BaseModel)


class ActionInput(BaseModel, Generic[ParametersType]):
    action_config: ActionConfig
    conversation_id: str
    params: ParametersType
    user_message_tracker: Optional[asyncio.Event] = None

    class Config:
        arbitrary_types_allowed = True


class ActionStart(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_input: ActionInput

    def to_string(self, include_timestamp: bool = False):
        if include_timestamp:
            return f"{Sender.ACTION_WORKER.name}: params={self.action_input.params.dict()} ({self.timestamp})"
        return f"{Sender.ACTION_WORKER.name}: params={self.action_input.params.dict()}"


ResponseType = TypeVar("ResponseType", bound=BaseModel)


class ActionOutput(BaseModel, Generic[ResponseType]):
    action_type: str
    response: ResponseType


class ActionFinish(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_output: ActionOutput

    def to_string(self, include_timestamp: bool = False):
        if include_timestamp:
            return f"{Sender.ACTION_WORKER.name}: action_type='{self.action_type}' response={self.action_output.response.dict()} ({self.timestamp})"
        return f"{Sender.ACTION_WORKER.name}: action_type='{self.action_type}' response={self.action_output.response.dict()}"


class FunctionFragment(BaseModel):
    name: str
    arguments: str


class FunctionCall(BaseModel):
    name: str
    arguments: str


class VonagePhoneCallActionInput(ActionInput[ParametersType]):
    vonage_uuid: str


class TwilioPhoneCallActionInput(ActionInput[ParametersType]):
    twilio_sid: str


ResponseType = TypeVar("ResponseType", bound=BaseModel)


class ActionOutput(BaseModel, Generic[ResponseType]):
    action_type: str
    response: ResponseType
