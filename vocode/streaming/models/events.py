from enum import Enum
from vocode.streaming.models.model import TypedModel


class Sender(str, Enum):
    HUMAN = "human"
    BOT = "bot"
    ACTION_WORKER = "action_worker"
    VECTOR_DB = "vector_db"


class EventType(str, Enum):
    TRANSCRIPT = "event_transcript"
    TRANSCRIPT_COMPLETE = "event_transcript_complete"
    PHONE_CALL_CONNECTED = "event_phone_call_connected"
    PHONE_CALL_ENDED = "event_phone_call_ended"
    RECORDING = "event_recording"


class Event(TypedModel):
    conversation_id: str


class PhoneCallConnectedEvent(Event, type=EventType.PHONE_CALL_CONNECTED):
    to_phone_number: str
    from_phone_number: str


class PhoneCallEndedEvent(Event, type=EventType.PHONE_CALL_ENDED):
    conversation_minutes: float = 0


class RecordingEvent(Event, type=EventType.RECORDING):
    recording_url: str
