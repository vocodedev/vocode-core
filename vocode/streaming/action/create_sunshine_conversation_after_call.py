import logging
from typing import Type

from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CreateSunshineConversationAfterCallActionConfig(
    ActionConfig, type=ActionType.CREATE_SUNSHINE_CONVERSATION_AFTER_CALL
):
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )


class CreateSunshineConversationAfterCallParameters(BaseModel):
    handoff_information: str = Field(
        ...,
        description="The information passed to a human agent when the support ticket is created",
    )


class CreateSunshineConversationAfterCallResponse(BaseModel):
    status: str = Field(None, description="The response received from the recipient")


class CreateSunshineConversationAfterCall(
    BaseAction[
        CreateSunshineConversationAfterCallActionConfig,
        CreateSunshineConversationAfterCallParameters,
        CreateSunshineConversationAfterCallResponse,
    ]
):
    description: str = "Create a sunshine conversation with a human support agent"
    parameters_type: Type[CreateSunshineConversationAfterCallParameters] = (
        CreateSunshineConversationAfterCallParameters
    )
    response_type: Type[CreateSunshineConversationAfterCallResponse] = (
        CreateSunshineConversationAfterCallResponse
    )

    async def run(
        self, action_input: ActionInput[CreateSunshineConversationAfterCallParameters]
    ) -> ActionOutput[CreateSunshineConversationAfterCallResponse]:
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CreateSunshineConversationAfterCallResponse(
                status="Sunshine conversation will be created after the call"
            ),
        )
