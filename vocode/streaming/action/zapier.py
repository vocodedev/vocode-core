import asyncio
import json
import logging
import os
import traceback
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
    params: dict = Field(
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
            "preview_only": False,
            "additionalProp1": {},
        }
        # Add each key-value pair from params to the body
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception as e:
                raise ValueError(f"Failed to decode params: {str(e)}")
        for key, value in params.items():
            body[key] = value

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            logger.info(
                f"Attempt {attempt + 1} of {max_retries} to execute Zapier action"
            )
            try:
                async with httpx.AsyncClient(
                    timeout=30.0
                ) as client:  # Increased timeout
                    response = await client.post(url, json=body, headers=headers)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                error_details = e.response.text
                try:
                    error_json = e.response.json()
                    if isinstance(error_json, dict):
                        error_details = json.dumps(error_json, indent=2)
                except ValueError:
                    pass
                if attempt == max_retries - 1:
                    return {
                        "error": f"HTTP error executing Zapier action: {e.response.status_code} {e.response.reason_phrase}",
                        "details": error_details,
                    }
            except (httpx.RequestError, httpx.ReadTimeout) as e:
                if attempt == max_retries - 1:
                    return {
                        "error": f"Network error executing Zapier action: {str(e)}",
                        "details": f"Request failed: {e.__class__.__name__} - {str(e)}",
                    }
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        "error": f"Unexpected error executing Zapier action: {str(e)}",
                        "details": f"Exception type: {type(e).__name__}, Traceback: {traceback.format_exc()}",
                    }

            # Wait before retrying
            await asyncio.sleep(retry_delay * (2**attempt))  # Exponential backoff

        return {
            "error": "Max retries reached",
            "details": "Failed to execute Zapier action after multiple attempts",
        }

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
