import os
from typing import Optional, Type
from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionInput, ActionOutput
from twilio.rest import Client as TwilioClient
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)


class TransferCallParameters(BaseModel):
    pass


class TransferCallResponse(BaseModel):
    status: str = Field("success", description="status of the transfer")


class TransferCall(BaseAction[TransferCallParameters, TransferCallResponse]):
    description: str = "transfers the call. use when you need to connect the active call to another phone line."
    action_type: str = "action_transfer_call"
    parameters_type: Type[TransferCallParameters] = TransferCallParameters
    response_type: Type[TransferCallResponse] = TransferCallResponse

    def __init__(self, to_phone: str, **kwargs):
        super().__init__(**kwargs)
        self.to_phone = to_phone
        # TODO: need to support all config managers
        self.config_manager = RedisConfigManager()

    async def run(
        self, action_input: ActionInput[TransferCallParameters]
    ) -> ActionOutput[TransferCallResponse]:
        call_config = await self.config_manager.get_config(action_input.conversation_id)

        if call_config is None:
            raise Exception("no call config found")
        twilio_call_sid = getattr(call_config, "twilio_sid", None)

        if twilio_call_sid is None:
            raise Exception("no call sid found")

        twilio_client = TwilioClient(
            os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
        )

        twilio_client.calls(twilio_call_sid).update(
            twiml="<Response><Dial>{to_phone}</Dial></Response>".format(
                to_phone=self.to_phone
            )
        )

        return ActionOutput(
            action_type=self.action_type,
            response=TransferCallResponse(status="success"),
        )
