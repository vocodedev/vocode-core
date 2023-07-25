from app.lib.models.api.action import ActionConfig
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.nylas_send_email import (
    NylasSendEmail,
    NylasSendEmailActionConfig,
)
from vocode.streaming.models.actions import ActionType


class ActionFactory:
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        if isinstance(action_config, NylasSendEmailActionConfig):
            return NylasSendEmail(action_config, should_respond=True)
        else:
            raise Exception("Invalid action type")
