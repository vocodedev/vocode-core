import os
from typing import Type

from pydantic import BaseModel, Field
from twilio.rest import Client as TwilioClient

from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)


class TransferCallActionConfig(ActionConfig):
    action_type: str = ActionType.TRANSFER_CALL
    to_phone: str


class TransferCallParameters(BaseModel):
    pass


class TransferCallResponse(BaseModel):
    status: str = Field("success", description="status of the transfer")


class TransferCall(
    TwilioPhoneCallAction[
        TransferCallActionConfig, TransferCallParameters, TransferCallResponse
    ]
):
    description: str = "transfers the call. use when you need to connect the active call to another phone line."
    parameters_type: Type[TransferCallParameters] = TransferCallParameters
    response_type: Type[TransferCallResponse] = TransferCallResponse

    async def run(
        self, action_input: ActionInput[TransferCallParameters]
    ) -> ActionOutput[TransferCallResponse]:
        twilio_call_sid = self.get_twilio_sid(action_input)

        twilio_client = TwilioClient(
            os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
        )

        # TODO: this is a blocking call, use aiohttp to do this asynchronously
        twilio_client.calls(twilio_call_sid).update(
            twiml="<Response><Dial>{to_phone}</Dial></Response>".format(
                to_phone=self.action_config.to_phone
            )
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=TransferCallResponse(status="success"),
        )
