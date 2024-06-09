import logging
import os
from typing import Type

from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.models.telephony import TwilioConfig

from telephony_app.integrations.twilio.twilio_webhook_client import trigger_twilio_webhook

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
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )


class ForwardCallToMoovsParameters(BaseModel):
    pass


class ForwardCallToMoovsResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")
    ending_phrase: str = Field(None, description="What the model should say when it has executed the function call")

class ForwardCallToMoovs(
    BaseAction[
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

    async def forward_call_to_moovs(self, action_config: ForwardCallToMoovsActionConfig):
        return await trigger_twilio_webhook(
            to=action_config.to_phone,
            from_=action_config.from_phone,
            call_sid=action_config.telephony_id,
            account_sid=action_config.twilio_config.account_sid,
            webhook_url=os.getenv("MOOVS_CALL_FORWARDING_ENDPOINT")
        )


    async def run(
            self, action_input: ActionInput[ForwardCallToMoovsActionConfig]
    ) -> ActionOutput[ForwardCallToMoovsResponse]:
        action_config = ForwardCallToMoovsActionConfig(**action_input.action_config.dict())
        response = await self.forward_call_to_moovs(action_config)
        if "error" in str(response).lower():
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=ForwardCallToMoovsResponse(
                    status=f"Failed to forward {action_input.params.from_phone} to registered representatives. "
                           f"Error: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=ForwardCallToMoovsResponse(
                status=f"We have forwarded the phone call. Response: {response}",
                ending_phrase="I have forwarded the phone call. Please hold."
            ),
        )
