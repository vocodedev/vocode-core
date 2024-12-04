import base64
from enum import Enum
from typing import Optional

from vocode.streaming.models.client_backend import InputAudioConfig, OutputAudioConfig

from .agent import AgentConfig
from .events import Sender
from .model import TypedModel
from .synthesizer import SynthesizerConfig
from .transcriber import TranscriberConfig
from .transcript import TranscriptEvent


class WebSocketMessageType(str, Enum):
    BASE = "websocket_base"
    START = "websocket_start"
    AUDIO = "websocket_audio"
    TRANSCRIPT = "websocket_transcript"
    READY = "websocket_ready"
    STOP = "websocket_stop"
    AUDIO_CONFIG_START = "websocket_audio_config_start"


class WebSocketMessage(TypedModel, type=WebSocketMessageType.BASE):  # type: ignore
    pass


class AudioMessage(WebSocketMessage, type=WebSocketMessageType.AUDIO):  # type: ignore
    data: str

    @classmethod
    def from_bytes(cls, chunk: bytes):
        return cls(data=base64.b64encode(chunk).decode("utf-8"))

    def get_bytes(self) -> bytes:
        return base64.b64decode(self.data)


class TranscriptMessage(WebSocketMessage, type=WebSocketMessageType.TRANSCRIPT):  # type: ignore
    text: str
    sender: Sender
    timestamp: float

    @classmethod
    def from_event(cls, event: TranscriptEvent):
        return cls(text=event.text, sender=event.sender, timestamp=event.timestamp)


class StartMessage(WebSocketMessage, type=WebSocketMessageType.START):  # type: ignore
    transcriber_config: TranscriberConfig
    agent_config: AgentConfig
    synthesizer_config: SynthesizerConfig
    conversation_id: Optional[str] = None


class AudioConfigStartMessage(
    WebSocketMessage, type=WebSocketMessageType.AUDIO_CONFIG_START  # type: ignore
):
    input_audio_config: InputAudioConfig
    output_audio_config: OutputAudioConfig
    conversation_id: Optional[str] = None
    subscribe_transcript: Optional[bool] = None


class ReadyMessage(WebSocketMessage, type=WebSocketMessageType.READY):  # type: ignore
    pass


class StopMessage(WebSocketMessage, type=WebSocketMessageType.STOP):  # type: ignore
    pass
