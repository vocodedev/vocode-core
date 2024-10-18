from enum import Enum
from typing import Callable, Optional
from .model import TypedModel
from enum import Enum


class MessageType(str, Enum):
    BASE = "message_base"
    SSML = "message_ssml"


class BaseMessage(TypedModel, type=MessageType.BASE):
    text: str
    on_message_sent: Optional[Callable[[str], None]]


class SSMLMessage(BaseMessage, type=MessageType.SSML):
    ssml: str
