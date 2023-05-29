from enum import Enum
from .model import TypedModel
from enum import Enum


class MessageType(str, Enum):
    BASE = "message_base"
    SSML = "message_ssml"


class BaseMessage(TypedModel, type=MessageType.BASE):
    text: str
    metadata: dict = {}

class SSMLMessage(BaseMessage, type=MessageType.SSML):
    ssml: str
