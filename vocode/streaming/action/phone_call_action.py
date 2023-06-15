from typing import Dict, Any, TypeVar, Union
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionOutput,
    TwilioPhoneCallActionInput,
    VonagePhoneCallActionInput,
)


VonagePhoneCallActionInputType = TypeVar(
    "VonagePhoneCallActionInputType",
    bound=VonagePhoneCallActionInput,
)
TwilioPhoneCallActionInputType = TypeVar(
    "TwilioPhoneCallActionInputType",
    bound=TwilioPhoneCallActionInput,
)
PhoneCallActionOutputType = TypeVar("PhoneCallActionOutputType", bound=ActionOutput)


class VonagePhoneCallAction(
    BaseAction[VonagePhoneCallActionInputType, PhoneCallActionOutputType]
):
    def create_phone_call_action_input(
        self, conversation_id: str, params: Dict[str, Any], vonage_uuid: str
    ) -> VonagePhoneCallActionInputType:
        if "user_message" in params:
            del params["user_message"]
        return self.action_input_type(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.action_input_type.Parameters(**params),
            vonage_uuid=vonage_uuid,
        )


class TwilioPhoneCallAction(
    BaseAction[TwilioPhoneCallActionInputType, PhoneCallActionOutputType]
):
    def create_phone_call_action_input(
        self, conversation_id: str, params: Dict[str, Any], twilio_sid: str
    ) -> TwilioPhoneCallActionInputType:
        if "user_message" in params:
            del params["user_message"]
        return self.action_input_type(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.action_input_type.Parameters(**params),
            twilio_sid=twilio_sid,
        )
