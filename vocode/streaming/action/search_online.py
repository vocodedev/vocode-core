import asyncio
import json
import logging
import os
import traceback
import httpx
from typing import Type
from pydantic import BaseModel, Field

from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
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


class SearchOnlineActionConfig(ActionConfig, type=ActionType.SEARCH_ONLINE):
    starting_phrase: str


class SearchOnlineParameters(BaseModel):
    query: str = Field(
        ..., description="The search query to be sent to the online search API"
    )


class SearchOnlineResponse(BaseModel):
    query: str = Field(..., description="The search query that was sent")
    response: str = Field(..., description="The response from the online search API")


class SearchOnline(
    BaseAction[SearchOnlineActionConfig, SearchOnlineParameters, SearchOnlineResponse]
):
    description: str = (
        "searches online using the provided query and returns the response"
    )
    parameters_type: Type[SearchOnlineParameters] = SearchOnlineParameters
    response_type: Type[SearchOnlineResponse] = SearchOnlineResponse

    async def search_online(self, query: str) -> str:
        """
        Searches online using the provided query and returns the response.

        :param query: The search query to be sent to the online search API
        """
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer pplx-6887a6a110129d0492eb8eab12debc1cca1ceda46e139c"
            + str(52 % 20),
        }
        body = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "user",
                    "content": query,
                }
            ],
            "temperature": 0.3,
        }

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            logger.info(
                f"Attempt {attempt + 1} of {max_retries} to execute online search"
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=body, headers=headers)
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                error_details = e.response.text
                try:
                    error_json = e.response.json()
                    if isinstance(error_json, dict):
                        error_details = json.dumps(error_json, indent=2)
                except ValueError:
                    pass
                if attempt == max_retries - 1:
                    return f"HTTP error executing online search: {e.response.status_code} {e.response.reason_phrase}. Details: {error_details}"
            except (httpx.RequestError, httpx.ReadTimeout) as e:
                if attempt == max_retries - 1:
                    return f"Network error executing online search: {str(e)}. Details: Request failed: {e.__class__.__name__} - {str(e)}"
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"Unexpected error executing online search: {str(e)}. Details: Exception type: {type(e).__name__}, Traceback: {traceback.format_exc()}"

            # Wait before retrying
            await asyncio.sleep(retry_delay * (2**attempt))  # Exponential backoff

        return "Max retries reached. Failed to execute online search after multiple attempts."

    async def run(
        self, action_input: ActionInput[SearchOnlineParameters]
    ) -> ActionOutput[SearchOnlineResponse]:
        query = action_input.params.query
        response_content = await self.search_online(query=query)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SearchOnlineResponse(query=query, response=response_content),
        )
