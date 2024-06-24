import logging
import os
from typing import Type, Dict

import aiohttp
from aiohttp import BasicAuth
from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.integrations.hello_sugar.hello_sugar_location_getter import (
    get_cached_hello_sugar_locations,
    search_all_locations,
)
from vocode.streaming.models.telephony import TwilioConfig


class SendHelloSugarBookingInstructionsActionConfig(
    ActionConfig, type=ActionType.SEND_HELLO_SUGAR_BOOKING_INSTRUCTIONS
):
    twilio_config: TwilioConfig
    from_phone: str
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )


class SendHelloSugarBookingInstructionsParameters(BaseModel):
    to_phone: str
    location: str


class SendHelloSugarBookingInstructionsResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class SendHelloSugarBookingInstructions(
    BaseAction[
        SendHelloSugarBookingInstructionsActionConfig,
        SendHelloSugarBookingInstructionsParameters,
        SendHelloSugarBookingInstructionsResponse,
    ]
):
    description: str = (
        "sends a text message to a phone number about the booking instructions for a specific location"
    )
    parameters_type: Type[SendHelloSugarBookingInstructionsParameters] = (
        SendHelloSugarBookingInstructionsParameters
    )
    response_type: Type[SendHelloSugarBookingInstructionsResponse] = (
        SendHelloSugarBookingInstructionsResponse
    )

    async def send_hello_sugar_booking_instructions(self, to_phone, location):
        twilio_account_sid = self.action_config.twilio_config.account_sid
        twilio_auth_token = self.action_config.twilio_config.auth_token
        from_phone = self.action_config.from_phone
        if len(to_phone) == 9:
            to_phone = "1" + to_phone

        hello_sugar_locations = search_all_locations(
            query=location, location_data=get_cached_hello_sugar_locations()
        )

        logging.info(f"Searched for the following locations: {hello_sugar_locations}")
        if hello_sugar_locations:
            try:
                message = f"Hello, tap this link to book an appointment: {hello_sugar_locations[0]['booking_url']}"
                url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
                payload = {"To": to_phone, "From": from_phone, "Body": message}
                auth = BasicAuth(twilio_account_sid, twilio_auth_token)

                async with aiohttp.ClientSession(auth=auth) as session:
                    async with session.post(url, data=payload) as response:
                        if response.status != 201:
                            response = await response.text()
                            return response
                        else:
                            return await response.json()
            except ValueError as e:
                complete_error_message = f"Error finding location: {e}"
                logging.error(complete_error_message)
                return complete_error_message
            except Exception as e:
                return f"Error sending text message: {e}"

    async def run(
        self, action_input: ActionInput[SendHelloSugarBookingInstructionsParameters]
    ) -> ActionOutput[SendHelloSugarBookingInstructionsResponse]:
        location = action_input.params.location
        to_phone = action_input.params.to_phone
        response = await self.send_hello_sugar_booking_instructions(to_phone, location)
        # response = await self.wait_for_response(self.action_config.to_phone)
        if 200 <= response.status < 300:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SendHelloSugarBookingInstructionsResponse(
                    status=f"Message to {to_phone} has been sent successfully with the content: '{location}'."
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendHelloSugarBookingInstructionsResponse(
                status=f"Failed to send message to {to_phone}. Error: {response}"
            ),
        )
