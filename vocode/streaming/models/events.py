from enum import Enum
from typing import Optional
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
    ACTION = "event_action"
    VOICEMAIL = "event_voicemail"


class Event(TypedModel):
    conversation_id: str


class PhoneCallConnectedEvent(Event, type=EventType.PHONE_CALL_CONNECTED):
    to_phone_number: str
    from_phone_number: str


class PhoneCallEndedEvent(Event, type=EventType.PHONE_CALL_ENDED):
    conversation_minutes: float = 0


class RecordingEvent(Event, type=EventType.RECORDING):
    recording_url: str


class ActionEvent(Event, type=EventType.ACTION):
    action_input: Optional[dict] = None
    action_output: Optional[dict] = None

#voicemail Event to send voicemail message if the person doesn't picks up  the call 
class VoicemailEvent(Event, type=EventType.VOICEMAIL):
    
    to_phone_number: str
    from_phone_number: str
    



