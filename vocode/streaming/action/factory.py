from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.nylas_send_email import NylasSendEmail
from vocode.streaming.models.actions import ActionType


class ActionFactory:
    def create_action(self, action_type):
        if action_type == ActionType.NYLAS_SEND_EMAIL:
            return NylasSendEmail()
        else:
            raise Exception("Invalid action type")
