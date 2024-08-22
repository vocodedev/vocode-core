import asyncio
import json
import logging
import os
import traceback
import httpx
from typing import Type, Dict, Any, List
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
    zapier_name: str = Field(..., description="The Zapier action name to be executed")
    params: dict = Field(
        ..., description="Parameters for the Zapier action as a DICT-encoded string"
    )


class ZapierResponse(BaseModel):
    status: str = Field(..., description="The status of the Zapier action execution")
    response: Dict[str, Any] = Field(..., description="The response from Zapier")


class ZapierAction(BaseModel):
    id: str
    operation_id: str
    description: str
    params: Dict[str, str]


class Zapier(BaseAction[ZapierActionConfig, ZapierParameters, ZapierResponse]):
    description: str = "Executes a Zapier action and returns the response"
    parameters_type: Type[ZapierParameters] = ZapierParameters
    response_type: Type[ZapierResponse] = ZapierResponse

    async def get_zapier_actions(self) -> List[ZapierAction]:
        url = "https://actions.zapier.com/api/v1/exposed/"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.action_config.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return [ZapierAction(**action) for action in data["results"]]

    async def execute_zapier_action(
        self, action_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        url = f"https://actions.zapier.com/api/v1/exposed/{action_id}/execute/"
        logger.error(f"URL: {url}")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.action_config.api_key,
        }
        body = {"instructions": "Run the action.", "preview_only": False, **params}

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            logger.info(
                f"Attempt {attempt + 1} of {max_retries} to execute Zapier action"
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
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

            await asyncio.sleep(retry_delay * (2**attempt))  # Exponential backoff

        return {
            "error": "Max retries reached",
            "details": "Failed to execute Zapier action after multiple attempts",
        }

    async def run(
        self, action_input: ActionInput[ZapierParameters]
    ) -> ActionOutput[ZapierResponse]:
        logger.debug(f"Action input: {action_input}")
        actions = await self.get_zapier_actions()
        action = next(
            (a for a in actions if a.description == action_input.params.zapier_name),
            None,
        )
        logger.debug(f"Action: {action}")

        if not action:
            logger.error(f"Action '{action_input.params.zapier_name}' not found")
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=ZapierResponse(
                    status="error",
                    response={
                        "error": f"Action '{action_input.params.zapier_name}' not found"
                    },
                ),
            )
        params = action_input.params.params
        response_content = await self.execute_zapier_action(
            action_id=action.id, params=params
        )
        logger.debug(f"Response: {response_content}")

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=ZapierResponse(status="success", response=response_content),
        )
