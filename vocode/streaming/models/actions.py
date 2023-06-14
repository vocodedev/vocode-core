from enum import Enum
from regex import B
from vocode.streaming.models.model import BaseModel


class ActionType(str, Enum):
    BASE = "action_base"
    NYLAS_SEND_EMAIL = "action_nylas_send_email"


class ActionInput(BaseModel):
    class Parameters(BaseModel):
        pass

    action_type: str
    conversation_id: str
    params: Parameters


class ActionOutput(BaseModel):
    class Response(BaseModel):
        pass

    action_type: str
    response: Response
