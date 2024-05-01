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

from telephony_app.integrations.boulevard_client import retrieve_next_appointment_by_phone_number, get_lost_directions
from telephony_app.utils.twilio_call_helper import get_twilio_config


class SendHelloSugarDirectionsActionConfig(
    ActionConfig, type=ActionType.SEND_HELLO_SUGAR_DIRECTIONS
):
    credentials: Dict
    from_phone: str
    twilio_account_sid: str


class SendHelloSugarDirectionsParameters(BaseModel):
    to_phone: str


class SendHelloSugarDirectionsResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class SendHelloSugarDirections(
    BaseAction[
        SendHelloSugarDirectionsActionConfig,
        SendHelloSugarDirectionsParameters,
        SendHelloSugarDirectionsResponse,
    ]
):
    description: str = (
        "sends a text message to a phone number about the directions to get to a specific location"
    )
    parameters_type: Type[SendHelloSugarDirectionsParameters] = (
        SendHelloSugarDirectionsParameters
    )
    response_type: Type[SendHelloSugarDirectionsResponse] = (
        SendHelloSugarDirectionsResponse
    )

    async def send_hello_sugar_directions(self, to_phone):
        twilio_config = await get_twilio_config(credentials=self.action_config.credentials,
                                                twilio_account_sid=self.action_config.twilio_account_sid)
        twilio_account_sid = twilio_config.account_sid
        twilio_auth_token = twilio_config.auth_token
        from_phone = self.action_config.from_phone
        # if to_phone has 9 digits, add +1 to the beginning
        if len(to_phone) == 9:
            to_phone = "1" + to_phone

        next_appointment = retrieve_next_appointment_by_phone_number(to_phone)
        logging.info(f"The next appointment's details are {next_appointment}")
        if next_appointment:
            try:
                lost_directions = get_lost_directions(next_appointment)
                logging.info(f"The directions to the destination are: {lost_directions}")
                message = f"To reach Hello Sugar: {lost_directions}"
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
        return f"Error finding next appointment: client does not have an upcoming appointment"

    async def run(
            self, action_input: ActionInput[SendHelloSugarDirectionsParameters]
    ) -> ActionOutput[SendHelloSugarDirectionsResponse]:
        to_phone = action_input.params.to_phone
        response = await self.send_hello_sugar_directions(to_phone)
        if "error" in str(response).lower():
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SendHelloSugarDirectionsResponse(
                    status=f"Failed to send message to {to_phone}. Error: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendHelloSugarDirectionsResponse(
                status=f"Directions to their next appointment location have been sent via text to: {to_phone}. "
                       f"The messages sent is: {response}"
            ),
        )
