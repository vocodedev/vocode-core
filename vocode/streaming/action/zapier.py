import json
import logging
import os
import httpx
from typing import Type, Dict, Any
from pydantic import BaseModel, Field

from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.action.base_action import BaseAction


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ZapierActionConfig(ActionConfig, type=ActionType.ZAPIER):
    starting_phrase: str
    api_key: str


class ZapierParameters(BaseModel):
    exposed_app_action_id: str = Field(
        ..., description="The Zapier action ID to be executed"
    )
    params: str = Field(
        ..., description="Parameters for the Zapier action as a DICT-encoded string"
    )


class ZapierResponse(BaseModel):
    status: str = Field(..., description="The status of the Zapier action execution")
    response: Dict[str, Any] = Field(..., description="The response from Zapier")


class Zapier(BaseAction[ZapierActionConfig, ZapierParameters, ZapierResponse]):
    description: str = "Executes a Zapier action and returns the response"
    parameters_type: Type[ZapierParameters] = ZapierParameters
    response_type: Type[ZapierResponse] = ZapierResponse

    async def execute_zapier_action(
        self, action: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes a Zapier action using the provided parameters.

        :param action: The Zapier action to be executed
        :param params: Parameters for the Zapier action
        """
        url = f"https://actions.zapier.com/api/v1/exposed/{action}/execute/"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.action_config.api_key,
        }
        body = {
            "instructions": f"Run the action.",
            # "app": self.action_config.app, goes in the url atleast in v1 url
            # "action": action,
            # "action_type": "write", #not needed in v1
            # "authentication_id": self.action_config.authentication_id,
            "preview_only": False,  # needed in v1
            "additionalProp1": {},  # needed in v1
            # "account_id": self.action_config.account_id, i dont think this is needed
        }
        # Add each key-value pair from params to the body
        # if params is a string, decode it to a dict
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception as e:
                raise ValueError(f"Failed to decode params: {str(e)}")
        for key, value in params.items():
            body[key] = value
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"error": f"Error executing Zapier action: {str(e)}"}

    async def run(
        self, action_input: ActionInput[ZapierParameters]
    ) -> ActionOutput[ZapierResponse]:
        action = action_input.params.exposed_app_action_id
        params = action_input.params.params
        response_content = await self.execute_zapier_action(
            action=action, params=params
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=ZapierResponse(status="success", response=response_content),
        )
