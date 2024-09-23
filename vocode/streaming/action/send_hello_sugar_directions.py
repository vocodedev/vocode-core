import logging
from typing import Dict, Type

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
from vocode.streaming.models.telephony import TwilioConfig

from telephony_app.integrations.boulevard.boulevard_client import (
    get_lost_directions,
    retrieve_next_appointment_by_phone_number,
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SendHelloSugarDirectionsActionConfig(
    ActionConfig, type=ActionType.SEND_HELLO_SUGAR_DIRECTIONS
):
    twilio_config: TwilioConfig
    from_phone: str
    business_id: str
    timezone: str
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )


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
        twilio_account_sid = self.action_config.twilio_config.account_sid
        twilio_auth_token = self.action_config.twilio_config.auth_token
        from_phone = self.action_config.from_phone
        # if to_phone has 9 digits, add +1 to the beginning
        if len(to_phone) == 9:
            to_phone = "1" + to_phone

        next_appointment = await retrieve_next_appointment_by_phone_number(
            to_phone, self.action_config.timezone, self.action_config.business_id
        )
        logger.info(f"The next appointment's details are {next_appointment}")
        if next_appointment:
            try:
                lost_directions = get_lost_directions(next_appointment)
                logger.info(f"The directions to the destination are: {lost_directions}")
                message = f"To reach Hello Sugar: {lost_directions}"
                url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
                payload = {"To": to_phone, "From": from_phone, "Body": message}
                auth = BasicAuth(twilio_account_sid, twilio_auth_token)

                async with aiohttp.ClientSession(auth=auth) as session:
                    async with session.post(url, data=payload) as response:
                        return response
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
        if response and 200 <= response.status < 300:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SendHelloSugarDirectionsResponse(
                    status=f"Directions to their next appointment location have been sent via text to: {to_phone}. "
                    f"The message sent is: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SendHelloSugarDirectionsResponse(
                status=f"Failed to send message to {to_phone}. Error: {response}"
            ),
        )
