from typing import Dict, Sequence, Type

from vocode_velocity.streaming.action.abstract_factory import AbstractActionFactory
from vocode_velocity.streaming.action.base_action import BaseAction
from vocode_velocity.streaming.action.dtmf import TwilioDTMF, VonageDTMF
from vocode_velocity.streaming.action.end_conversation import EndConversation
from vocode_velocity.streaming.action.execute_external_action import ExecuteExternalAction
from vocode_velocity.streaming.action.phone_call_action import (
    TwilioPhoneConversationAction,
    VonagePhoneConversationAction,
)
from vocode_velocity.streaming.action.record_email import RecordEmail
from vocode_velocity.streaming.action.transfer_call import TwilioTransferCall, VonageTransferCall
from vocode_velocity.streaming.action.wait import Wait
from vocode_velocity.streaming.models.actions import ActionConfig, ActionType

CONVERSATION_ACTIONS: Dict[ActionType, Type[BaseAction]] = {
    ActionType.END_CONVERSATION: EndConversation,
    ActionType.RECORD_EMAIL: RecordEmail,
    ActionType.WAIT: Wait,
    ActionType.EXECUTE_EXTERNAL_ACTION: ExecuteExternalAction,
}

VONAGE_ACTIONS: Dict[ActionType, Type[VonagePhoneConversationAction]] = {
    ActionType.TRANSFER_CALL: VonageTransferCall,
    ActionType.DTMF: VonageDTMF,
}

TWILIO_ACTIONS: Dict[ActionType, Type[TwilioPhoneConversationAction]] = {
    ActionType.TRANSFER_CALL: TwilioTransferCall,
    ActionType.DTMF: TwilioDTMF,
}


class DefaultActionFactory(AbstractActionFactory):
    def __init__(self, actions: Sequence[ActionConfig] | dict = {}):

        self.action_configs_dict = {action.type: action for action in actions}
        self.actions = CONVERSATION_ACTIONS

    def create_action(self, action_config: ActionConfig):
        if action_config.type not in self.action_configs_dict:
            raise Exception("Action type not supported by Agent config.")

        action_class = self.actions[action_config.type]

        return action_class(action_config)
