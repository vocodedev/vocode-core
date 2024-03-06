import asyncio
import os
import aiohttp
from aiohttp import BasicAuth
from typing import Type
from pydantic import BaseModel, Field
from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)


class SendTextActionConfig(ActionConfig, type=ActionType.SEND_TEXT):
    to_phone: str
    message: str


class SendTextParameters(BaseModel):
    pass


class SendTextResponse(BaseModel):
    response: str = Field(None, description="The response received from the recipient")


class SendText(
    TwilioPhoneCallAction[SendTextActionConfig, SendTextParameters, SendTextResponse]
):
    description: str = (
        "sends a text message to a phone number and waits for a response for one minute or until one is received."
    )
    parameters_type: Type[SendTextParameters] = SendTextParameters
    response_type: Type[SendTextResponse] = SendTextResponse

    async def send_text(self, to_phone, message):
        twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_phone = os.environ["TWILIO_PHONE_NUMBER"]

        url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
        payload = {"To": to_phone, "From": from_phone, "Body": message}
        auth = BasicAuth(twilio_account_sid, twilio_auth_token)

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(url, data=payload) as response:
                if response.status != 201:
                    print(await response.text())
                    raise Exception("failed to send text message")
                else:
                    return await response.json()

    async def wait_for_response(self, to_phone, timeout=60):
        twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_phone = os.environ["TWILIO_PHONE_NUMBER"]

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
            params = {
                "To": from_phone,
                "From": to_phone,
                "PageSize": 1,
                "Page": 0,
            }
            auth = BasicAuth(twilio_account_sid, twilio_auth_token)

            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = data["messages"]
                        if messages:
                            return messages[0]["body"]
                    else:
                        print(await response.text())
                        raise Exception("failed to retrieve messages")

            await asyncio.sleep(5)  # Wait for 5 seconds before checking again

        return "No response received after 1 minute"

    async def run(
        self, action_input: ActionInput[SendTextParameters]
    ) -> ActionOutput[SendTextResponse]:
        await self.send_text(self.action_config.to_phone, self.action_config.message)
        response = await self.wait_for_response(self.action_config.to_phone)
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendTextResponse(response=response),
        )
