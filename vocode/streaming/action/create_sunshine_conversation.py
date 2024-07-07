import logging
from typing import Type

from pydantic import BaseModel, Field
from sunshine_conversations_client import MessagePostResponse
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.models.telephony import TwilioConfig

from telephony_app.integrations.zendesk.sunshine_client import sign_jwt, \
    fetch_integrations_with_filters_by_phone_number, create_new_conversation

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CreateSunshineConversationActionConfig(
    ActionConfig, type=ActionType.CREATE_SUNSHINE_CONVERSATION
):
    twilio_config: TwilioConfig
    from_phone: str  # the number that is calling us
    to_phone: str  # our inbound number
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )
    credentials: dict  # contains KEY_ID, SECRET, APP_ID


class CreateSunshineConversationParameters(BaseModel):
    handoff_information: str = Field(
        ..., description="The information passed to a human agent when the support ticket is created",
    )


class CreateSunshineConversationResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class CreateSunshineConversation(
    BaseAction[
        CreateSunshineConversationActionConfig,
        CreateSunshineConversationParameters,
        CreateSunshineConversationResponse,
    ]
):
    description: str = (
        "Create a sunshine conversation with a human support agent"
    )
    parameters_type: Type[CreateSunshineConversationParameters] = (
        CreateSunshineConversationParameters
    )
    response_type: Type[CreateSunshineConversationResponse] = (
        CreateSunshineConversationResponse
    )

    # Create a Sunshine conversation and notify the user via text about the next steps
    async def create_sunshine_conversation(self, parameters: CreateSunshineConversationParameters) -> MessagePostResponse:
        key_id = self.action_config.credentials.get("KEY_ID")
        app_id = self.action_config.credentials.get("APP_ID")
        secret = self.action_config.credentials.get("SECRET")
        jwt_token = sign_jwt(key_id=key_id, secret=secret)

        # internal_phone_number is the store's phone number, which has twilio integrations specific to the number
        # when testing, hardcode the internal_phone_number to any store's phone_number
        desired_integration = await fetch_integrations_with_filters_by_phone_number(app_id=app_id,
                                                                                    jwt_token=jwt_token,
                                                                                    internal_phone_number=self.action_config.to_phone,
                                                                                    integration_type='twilio')
        integration_id = desired_integration['id']

        # TODO: Boulevard integration to find first name of customer + swap out first name
        # if not first_name:
        #     first_name = external_phone_number

        INITIAL_CUSTOMER_SERVICE_MESSAGE = "Hello Gorgeous! A team member will be reaching out via SMS within the next 7 minutes to help."

        return await create_new_conversation(app_id=app_id, internal_phone_number=self.action_config.to_phone,
                                             initial_internal_message=parameters.handoff_information,
                                             integration_id=integration_id,
                                             key_id=key_id,
                                             secret=secret,
                                             initial_external_message=INITIAL_CUSTOMER_SERVICE_MESSAGE,
                                             external_phone_number=self.action_config.from_phone,
                                             first_name=self.action_config.from_phone)

    async def run(self,
                  action_input: ActionInput[CreateSunshineConversationParameters]
                  ) -> ActionOutput[CreateSunshineConversationResponse]:
        response = await self.create_sunshine_conversation(parameters=action_input.params)
        if response:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=CreateSunshineConversationResponse(
                    status=f"Sunshine conversation has been started for phone number: {self.action_config.from_phone}. "
                           f"Response is: {response}"
                ),
            )
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CreateSunshineConversationResponse(
                status=f"Failed to start sunshine conversation with {self.action_config.from_phone}."
            ),
        )
