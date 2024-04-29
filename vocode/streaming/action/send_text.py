import asyncio
import os
import aiohttp
from aiohttp import BasicAuth
from typing import Type
from pydantic import BaseModel, Field
from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.action.base_action import BaseAction

from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)


class SendTextActionConfig(ActionConfig, type=ActionType.SEND_TEXT):
    from_phone: str


class SendTextParameters(BaseModel):
    to_phone: str
    contents: str


class SendTextResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class SendText(BaseAction[SendTextActionConfig, SendTextParameters, SendTextResponse]):
    description: str = (
        "sends a text message to a phone number and waits for a response for one minute or until one is received."
    )
    parameters_type: Type[SendTextParameters] = SendTextParameters
    response_type: Type[SendTextResponse] = SendTextResponse

    async def sms(self, to_phone, contents):
        twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_phone = self.action_config.from_phone
        # if to_phone has 9 digits, add +1 to the beginning
        if len(to_phone) == 9:
            to_phone = "1" + to_phone

        url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
        payload = {"To": to_phone, "From": from_phone, "Body": contents}
        try:
            auth = BasicAuth(twilio_account_sid, twilio_auth_token)

            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.post(url, data=payload) as response:
                    if response.status != 201:
                        response = await response.text()
                        return response
                    else:
                        return await response.json()
        except Exception as e:
            return "Error sending text message: " + str(e)

    async def wait_for_response(self, to_phone, timeout=60):
        twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_phone = self.action_config.from_phone

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
        contents = action_input.params.contents
        to_phone = action_input.params.to_phone
        response = await self.sms(to_phone, contents)
        # response = await self.wait_for_response(self.action_config.to_phone)
        if "error sending text message" in str(response).lower():
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SendTextResponse(
                    status=f"Failed to send message to {to_phone}. Error: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendTextResponse(
                status=f"Message to {to_phone} has been sent successfully with the content: '{contents}'."
            ),
        )
