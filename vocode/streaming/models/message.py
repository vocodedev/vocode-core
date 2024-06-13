from enum import Enum
from typing import Optional

from .model import TypedModel


class MessageType(str, Enum):
    BASE = "message_base"
    SSML = "message_ssml"
    BOT_BACKCHANNEL = "bot_backchannel"
    LLM_TOKEN = "llm_token"


class BaseMessage(TypedModel, type=MessageType.BASE):  # type: ignore
    text: str
    trailing_silence_seconds: float = 0.0
    cache_phrase: Optional[str] = None


class SSMLMessage(BaseMessage, type=MessageType.SSML):  # type: ignore
    ssml: str


class BotBackchannel(BaseMessage, type=MessageType.BOT_BACKCHANNEL):  # type: ignore
    pass


class LLMToken(BaseMessage, type=MessageType.LLM_TOKEN):  # type: ignore
    pass


class SilenceMessage(BotBackchannel):
    text: str = "<silence>"
    trailing_silence_seconds: float = 1.0
