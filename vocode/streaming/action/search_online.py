import logging
import os
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
            "Authorization": "Bearer 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",
        }
        body = {
            "model": "llama-3-sonar-small-32k-online",
            "messages": [
                {
                    "role": "user",
                    "content": query
                    + "\nYour answer should be a couple of sentences, max.",
                }
            ],
            "temperature": 0.7,
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                return f"Error searching online: {str(e)}"

    async def run(
        self, action_input: ActionInput[SearchOnlineParameters]
    ) -> ActionOutput[SearchOnlineResponse]:
        query = action_input.params.query
        response_content = await self.search_online(query=query)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SearchOnlineResponse(query=query, response=response_content),
        )
