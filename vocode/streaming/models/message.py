from typing import Literal, Optional

from pydantic import BaseModel

MessageType = Literal["message_base", "message_ssml", "bot_backchannel", "llm_token"]


class BaseMessage(BaseModel):
    type: MessageType = "message_base"
    text: str
    trailing_silence_seconds: float = 0.0
    cache_phrase: Optional[str] = None


class SSMLMessage(BaseMessage):
    type: Literal["message_ssml"] = "message_ssml"
    ssml: str


class BotBackchannel(BaseMessage):
    type: Literal["bot_backchannel"] = "bot_backchannel"


class LLMToken(BaseMessage):
    type: Literal["llm_token"] = "llm_token"


class SilenceMessage(BotBackchannel):
    text: str = "<silence>"
    trailing_silence_seconds: float = 1.0
