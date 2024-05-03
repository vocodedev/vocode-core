import asyncio
import os
import aiohttp

from aiohttp import BasicAuth
from typing import Type, Dict
from pydantic import BaseModel, Field

from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.utils.twilio_call_helper import get_twilio_config


class TransferCallActionConfig(ActionConfig, type=ActionType.TRANSFER_CALL):
    credentials: Dict
    twilio_account_sid: str
    starting_phrase: str


class TransferCallParameters(BaseModel):
    phone_number_to_transfer_to: str = Field(
        ...,
        description="The phone number to transfer the call to",
    )


class TransferCallResponse(BaseModel):
    status: str = Field("success", description="status of the transfer")


class TransferCall(
    TwilioPhoneCallAction[
        TransferCallActionConfig, TransferCallParameters, TransferCallResponse
    ]
):
    description: str = (
        "transfers the call. use when you need to connect the active call to another phone line."
    )
    parameters_type: Type[TransferCallParameters] = TransferCallParameters
    response_type: Type[TransferCallResponse] = TransferCallResponse

    async def transfer_call(self, twilio_call_sid, to_phone):
        twilio_config = await get_twilio_config(
            credentials=self.action_config.credentials,
            twilio_account_sid=self.action_config.twilio_account_sid,
        )
        twilio_account_sid = twilio_config.account_sid
        twilio_auth_token = twilio_config.auth_token

        url = "https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Calls/{twilio_auth_token}.json".format(
            twilio_account_sid=twilio_account_sid, twilio_auth_token=twilio_call_sid
        )

        twiml_data = "<Response><Dial>{to_phone}</Dial></Response>".format(
            to_phone=to_phone
        )

        payload = {"Twiml": twiml_data}

        auth = BasicAuth(twilio_account_sid, twilio_auth_token)

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(url, data=payload) as response:
                if response.status != 200:
                    print(await response.text())
                    raise Exception("failed to update call")
                else:
                    return await response.json()

    async def run(
        self, action_input: ActionInput[TransferCallParameters]
    ) -> ActionOutput[TransferCallResponse]:
        twilio_call_sid = self.get_twilio_sid(action_input)

        await asyncio.sleep(
            6.5
        )  # to provide small gap between speaking and transfer ring
        await self.transfer_call(
            twilio_call_sid=twilio_call_sid,
            to_phone=action_input.params.phone_number_to_transfer_to,
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=TransferCallResponse(status="success"),
        )
