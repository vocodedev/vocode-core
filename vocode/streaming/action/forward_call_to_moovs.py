import asyncio
import logging
import os
from typing import Type

from pydantic import BaseModel, Field
from starlette.datastructures import FormData
from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.models.telephony import TwilioConfig

from telephony_app.integrations.moovs.moovs_client import forward_call_to_moovs_operators

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ForwardCallToMoovsActionConfig(
    ActionConfig, type=ActionType.FORWARD_CALL_TO_MOOVS
):
    twilio_config: TwilioConfig
    from_phone: str  # the number that is calling us
    to_phone: str  # our inbound number
    telephony_id: str
    twilio_form_data: dict = Field(..., description="Twilio call form data")
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            FormData: lambda v: None  # Exclude FormData from serialization
        }


class ForwardCallToMoovsParameters(BaseModel):
    handoff_information: str = Field(
        ..., description="The information passed to a human agent when the call is forwarded",
    )


class ForwardCallToMoovsResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")

class ForwardCallToMoovs(
    TwilioPhoneCallAction[
        ForwardCallToMoovsActionConfig,
        ForwardCallToMoovsParameters,
        ForwardCallToMoovsResponse,
    ]
):
    description: str = (
        "Forwards the call to all drivers within corresponding company registered on Moovs"
    )
    parameters_type: Type[ForwardCallToMoovsParameters] = (
        ForwardCallToMoovsParameters
    )
    response_type: Type[ForwardCallToMoovsResponse] = (
        ForwardCallToMoovsResponse
    )

    async def forward_call_to_moovs(self, handoff_information: str):
        return await forward_call_to_moovs_operators(
            twilio_config=self.action_config.twilio_config,
            twilio_form_data_dict=self.action_config.twilio_form_data,
            webhook_url=os.getenv("MOOVS_CALL_FORWARDING_ENDPOINT"),
            handoff_information=handoff_information
        )

    async def run(
            self, action_input: ActionInput[ForwardCallToMoovsParameters]
    ) -> ActionOutput[ForwardCallToMoovsResponse]:

        # To give time for the AI to notify human about the call forwarding that is about to occur
        await asyncio.sleep(
            5.5
        )
        response = await self.forward_call_to_moovs(handoff_information=action_input.params.handoff_information)
        if response and 200 <= response.status < 300:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=ForwardCallToMoovsResponse(
                    status=f"We have forwarded the phone call. Response: {response}",
                ),
            )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=ForwardCallToMoovsResponse(
                status=f"Failed to forward {self.action_config.from_phone} to registered representatives. "
                       f"Error: {response}"
            ),
        )