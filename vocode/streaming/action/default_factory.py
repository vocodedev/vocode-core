from typing import Dict, Sequence, Type

from vocode.streaming.action.abstract_factory import AbstractActionFactory
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.dtmf import TwilioDTMF, VonageDTMF
from vocode.streaming.action.end_conversation import EndConversation
from vocode.streaming.action.execute_external_action import ExecuteExternalAction
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneConversationAction,
    VonagePhoneConversationAction,
)
from vocode.streaming.action.record_email import RecordEmail
from vocode.streaming.action.transfer_call import TwilioTransferCall, VonageTransferCall
from vocode.streaming.action.wait import Wait
from vocode.streaming.models.actions import ActionConfig, ActionType

CONVERSATION_ACTIONS: Dict[ActionType, Type[BaseAction]] = {
    "action_end_conversation": EndConversation,
    "action_record_email": RecordEmail,
    "action_wait": Wait,
    "action_external": ExecuteExternalAction,
}

VONAGE_ACTIONS: Dict[ActionType, Type[VonagePhoneConversationAction]] = {
    "action_transfer_call": VonageTransferCall,
    "action_dtmf": VonageDTMF,
}

TWILIO_ACTIONS: Dict[ActionType, Type[TwilioPhoneConversationAction]] = {
    "action_transfer_call": TwilioTransferCall,
    "action_dtmf": TwilioDTMF,
}


class DefaultActionFactory(AbstractActionFactory):
    def __init__(self):
        self.actions = CONVERSATION_ACTIONS  # TODO (DOW-119): StreamingConversationActionFactory

    def create_action(self, action_config: ActionConfig):
        if action_config.type not in self.actions:
            raise Exception("Action type not supported by Agent config.")

        action_class = self.actions[action_config.type]

        return action_class(action_config)


class DefaultTwilioPhoneConversationActionFactory(DefaultActionFactory):
    def __init__(self):
        self.actions = {**TWILIO_ACTIONS, **CONVERSATION_ACTIONS}


class DefaultVonagePhoneConversationActionFactory(DefaultActionFactory):
    def __init__(self):
        self.actions = {**VONAGE_ACTIONS, **CONVERSATION_ACTIONS}
