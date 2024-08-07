import base64
from abc import ABC
from enum import Enum
from typing import Any, Literal, Optional

from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.client_backend import InputAudioConfig, OutputAudioConfig

from .agent import AgentConfig
from .events import Sender
from .synthesizer import SynthesizerConfig
from .transcriber import TranscriberConfig
from .transcript import TranscriptEvent


class WebSocketMessage(AdaptiveObject, ABC):
    type: Any


class AudioMessage(WebSocketMessage):
    type: Literal["websocket_audio"] = "websocket_audio"
    data: str

    @classmethod
    def from_bytes(cls, chunk: bytes):
        return cls(data=base64.b64encode(chunk).decode("utf-8"))

    def get_bytes(self) -> bytes:
        return base64.b64decode(self.data)


class TranscriptMessage(WebSocketMessage):
    type: Literal["websocket_transcript"] = "websocket_transcript"
    text: str
    sender: Sender
    timestamp: float

    @classmethod
    def from_event(cls, event: TranscriptEvent):
        return cls(text=event.text, sender=event.sender, timestamp=event.timestamp)


class StartMessage(WebSocketMessage):
    type: Literal["websocket_start"] = "websocket_start"
    transcriber_config: TranscriberConfig
    agent_config: AgentConfig
    synthesizer_config: SynthesizerConfig
    conversation_id: Optional[str] = None


class AudioConfigStartMessage(WebSocketMessage):
    type: Literal["websocket_audio_config_start"] = "websocket_audio_config_start"
    input_audio_config: InputAudioConfig
    output_audio_config: OutputAudioConfig
    conversation_id: Optional[str] = None
    subscribe_transcript: Optional[bool] = None


class ReadyMessage(WebSocketMessage):
    type: Literal["websocket_ready"] = "websocket_ready"


class StopMessage(WebSocketMessage):
    type: Literal["websocket_stop"] = "websocket_stop"
