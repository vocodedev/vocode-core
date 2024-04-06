import asyncio
import logging
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

from telephony_app.integrations.hello_sugar.hello_sugar_location_getter import get_all_google_locations, \
    get_cached_hello_sugar_locations


class SendHelloSugarBookingInstructionsActionConfig(ActionConfig, type=ActionType.SEND_HELLO_SUGAR_BOOKING_INSTRUCTIONS):
    from_phone: str


class SendHelloSugarBookingInstructionsParameters(BaseModel):
    to_phone: str
    location: str


class SendHelloSugarBookingInstructionsResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class SendHelloSugarBookingInstructions(BaseAction[SendHelloSugarBookingInstructionsActionConfig, SendHelloSugarBookingInstructionsParameters, SendHelloSugarBookingInstructionsResponse]):
    description: str = (
        "sends a text message to a phone number about the booking instructions for a specific location"
    )
    parameters_type: Type[SendHelloSugarBookingInstructionsParameters] = SendHelloSugarBookingInstructionsParameters
    response_type: Type[SendHelloSugarBookingInstructionsResponse] = SendHelloSugarBookingInstructionsResponse

    async def send_hello_sugar_booking_instructions(self, to_phone, location):
        twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_phone = self.action_config.from_phone
        # if to_phone has 9 digits, add +1 to the beginning
        if len(to_phone) == 9:
            to_phone = "1" + to_phone

        hello_sugar_google_locations = get_all_google_locations(f"hello sugar | {location}")

        if hello_sugar_google_locations:
            searched_hello_sugar_location = hello_sugar_google_locations["places"][0]["id"]
            cached_hello_sugar_locations = get_cached_hello_sugar_locations()
            try:
                logging.error(f"The searched_hello_sugar_location is {searched_hello_sugar_location} while the location is {location}")
                if not location:
                    raise ValueError(f"Could not understand which location was being input. Please input a new location to book an appointment for.")
                if searched_hello_sugar_location not in cached_hello_sugar_locations:
                    raise ValueError(f"The location does not exist {searched_hello_sugar_location} in hello sugar's locations")

                message = f"The booking_url is {cached_hello_sugar_locations[searched_hello_sugar_location]['booking_url']}"
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
        if "error sending text message" in str(response).lower():
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SendHelloSugarBookingInstructionsResponse(
                    status=f"Failed to send message to {to_phone}. Error: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendHelloSugarBookingInstructionsResponse(
                status=f"Message to {to_phone} has been sent successfully with the content: '{location}'."
            ),
        )
