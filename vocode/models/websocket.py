import base64
from enum import Enum
from .model import TypedModel
from .transcriber import TranscriberConfig
from .agent import AgentConfig
from .synthesizer import SynthesizerConfig

class WebSocketMessageType(str, Enum):
    BASE = 'base'
    START = 'start'
    AUDIO = 'audio'
    READY = 'ready'
    STOP = 'stop'

class WebSocketMessage(TypedModel, type=WebSocketMessageType.BASE): pass

class AudioMessage(WebSocketMessage, type=WebSocketMessageType.AUDIO):
    data: str

    @classmethod
    def from_bytes(cls, chunk: bytes):
        return cls(data=base64.b64encode(chunk).decode('utf-8'))

    def get_bytes(self) -> bytes:
        return base64.b64decode(self.data)

class StartMessage(WebSocketMessage, type=WebSocketMessageType.START):
    transcriber_config: TranscriberConfig
    agent_config: AgentConfig
    synthesizer_config: SynthesizerConfig

class ReadyMessage(WebSocketMessage, type=WebSocketMessageType.READY):
    pass

class StopMessage(WebSocketMessage, type=WebSocketMessageType.STOP):
    pass