from typing import Any, Dict
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.nylas_send_email import (
    NylasSendEmail,
    NylasSendEmailActionInput,
)
from vocode.streaming.models.actions import ActionType


class ActionFactory:
    _actions = {
        ActionType.NYLAS_SEND_EMAIL.value: NylasSendEmail,
    }

    def create_action(self, action_type: str) -> BaseAction:
        if action_type not in self._actions:
            raise Exception(f"Action type {action_type} not found")
        return self._actions[action_type]()
