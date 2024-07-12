from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from pydantic import BaseModel

from vocode.streaming.models.adaptive_object import AdaptiveObject

if TYPE_CHECKING:
    from vocode.streaming.models.transcript import Transcript


class Sender(str, Enum):
    HUMAN = "human"
    BOT = "bot"
    ACTION_WORKER = "action_worker"
    VECTOR_DB = "vector_db"
    CONFERENCE = "conference"


class EventType(str, Enum):
    TRANSCRIPT = "event_transcript"
    TRANSCRIPT_COMPLETE = "event_transcript_complete"
    PHONE_CALL_CONNECTED = "event_phone_call_connected"
    PHONE_CALL_ENDED = "event_phone_call_ended"
    PHONE_CALL_DID_NOT_CONNECT = "event_phone_call_did_not_connect"
    RECORDING = "event_recording"
    ACTION = "event_action"


class Event(AdaptiveObject, ABC):
    type: Any
    conversation_id: str


class PhoneCallConnectedEvent(Event):
    type: Literal["event_phone_call_connected"] = "event_phone_call_connected"
    to_phone_number: str
    from_phone_number: str


class PhoneCallEndedEvent(Event):
    type: Literal["event_phone_call_ended"] = "event_phone_call_ended"
    conversation_minutes: float = 0


class PhoneCallDidNotConnectEvent(Event):
    type: Literal["event_phone_call_did_not_connect"] = "event_phone_call_did_not_connect"
    telephony_status: str


class RecordingEvent(Event):
    type: Literal["event_recording"] = "event_recording"
    recording_url: str


class ActionEvent(Event):
    type: Literal["event_action"] = "event_action"
    action_input: Optional[dict] = None
    action_output: Optional[dict] = None
