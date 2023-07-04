from typing import Dict, Any
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionInput,
    ActionOutput,
    ParametersType,
    ResponseType,
    TwilioPhoneCallActionInput,
    VonagePhoneCallActionInput,
)


class VonagePhoneCallAction(BaseAction[ParametersType, ResponseType]):
    def create_phone_call_action_input(
        self, conversation_id: str, params: Dict[str, Any], vonage_uuid: str
    ) -> VonagePhoneCallActionInput[ParametersType]:
        if "user_message" in params:
            del params["user_message"]
        return VonagePhoneCallActionInput(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.parameters_type(**params),
            vonage_uuid=vonage_uuid,
        )

    def get_vonage_uuid(self, action_input: ActionInput[ParametersType]) -> str:
        assert isinstance(action_input, VonagePhoneCallActionInput)
        return action_input.vonage_uuid


class TwilioPhoneCallAction(BaseAction[ParametersType, ResponseType]):
    def create_phone_call_action_input(
        self, conversation_id: str, params: Dict[str, Any], twilio_sid: str
    ) -> TwilioPhoneCallActionInput[ParametersType]:
        if "user_message" in params:
            del params["user_message"]
        return TwilioPhoneCallActionInput(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.parameters_type(**params),
            twilio_sid=twilio_sid,
        )

    def get_twilio_sid(self, action_input: ActionInput[ParametersType]) -> str:
        assert isinstance(action_input, TwilioPhoneCallActionInput)
        return action_input.twilio_sid
