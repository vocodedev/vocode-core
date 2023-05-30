from enum import Enum
from vocode.streaming.models.model import BaseModel


class ActionType(str, Enum):
    BASE = "action_base"
    NYLAS_SEND_EMAIL = "action_nylas_send_email"


class ActionInput(BaseModel):
    action_type: ActionType
    params: str
    conversation_id: str


class ActionOutput(BaseModel):
    action_type: ActionType
    response: str


class NylasSendEmailActionOutput(ActionOutput):
    action_type: ActionType = ActionType.NYLAS_SEND_EMAIL
