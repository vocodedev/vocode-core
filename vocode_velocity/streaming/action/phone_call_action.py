import asyncio
from typing import Any, Dict, Optional

from vocode.streaming.action.base_action import ActionConfigType, BaseAction
from vocode.streaming.models.actions import (
    ActionInput,
    ParametersType,
    ResponseType,
    TwilioPhoneConversationActionInput,
    VonagePhoneConversationActionInput,
)
from vocode.streaming.utils.state_manager import (
    TwilioPhoneConversationStateManager,
    VonagePhoneConversationStateManager,
)


class VonagePhoneConversationAction(BaseAction[ActionConfigType, ParametersType, ResponseType]):
    def create_phone_conversation_action_input(
        self,
        conversation_id: str,
        params: Dict[str, Any],
        vonage_uuid: str,
        user_message_tracker: Optional[asyncio.Event] = None,
    ) -> VonagePhoneConversationActionInput[ParametersType]:
        if "user_message" in params:
            del params["user_message"]
        return VonagePhoneConversationActionInput(
            action_config=self.action_config,
            conversation_id=conversation_id,
            params=self.parameters_type(**params),
            vonage_uuid=vonage_uuid,
            user_message_tracker=user_message_tracker,
        )

    def get_vonage_uuid(self, action_input: ActionInput[ParametersType]) -> str:
        assert isinstance(action_input, VonagePhoneConversationActionInput)
        return action_input.vonage_uuid

    def attach_conversation_state_manager(self, conversation_state_manager: Any):
        assert isinstance(conversation_state_manager, VonagePhoneConversationStateManager)
        self.conversation_state_manager = conversation_state_manager


class TwilioPhoneConversationAction(BaseAction[ActionConfigType, ParametersType, ResponseType]):
    def create_phone_conversation_action_input(
        self,
        conversation_id: str,
        params: Dict[str, Any],
        twilio_sid: str,
        user_message_tracker: Optional[asyncio.Event] = None,
    ) -> TwilioPhoneConversationActionInput[ParametersType]:
        if "user_message" in params:
            del params["user_message"]
        return TwilioPhoneConversationActionInput(
            action_config=self.action_config,
            conversation_id=conversation_id,
            params=self.parameters_type(**params),
            twilio_sid=twilio_sid,
            user_message_tracker=user_message_tracker,
        )

    def get_twilio_sid(self, action_input: ActionInput[ParametersType]) -> str:
        assert isinstance(action_input, TwilioPhoneConversationActionInput)
        return action_input.twilio_sid

    def attach_conversation_state_manager(self, conversation_state_manager: Any):
        assert isinstance(conversation_state_manager, TwilioPhoneConversationStateManager)
        self.conversation_state_manager = conversation_state_manager
