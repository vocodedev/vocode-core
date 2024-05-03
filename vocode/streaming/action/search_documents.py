import logging
import os
import httpx
from typing import Type
from pydantic import BaseModel, Field
from vocode import getenv
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


class SearchDocumentsActionConfig(ActionConfig, type=ActionType.SEARCH_DOCUMENTS):
    ai_profile_id: int = Field(
        ..., description="The profile ID to search documents for"
    )
    starting_phrase: str = Field(
        ..., description="What the agent should say when starting the action"
    )


class SearchDocumentsParameters(BaseModel):
    query: str = Field(..., description="The query to search the documents")


class SearchDocumentsResponse(BaseModel):
    query: str = Field(None, description="The query used for searching documents")
    answer: str = Field(None, description="The answer to the query")


class SearchDocuments(
    BaseAction[
        SearchDocumentsActionConfig,
        SearchDocumentsParameters,
        SearchDocumentsResponse,
    ]
):
    description: str = "Searches documents based on the agent profile and query"
    parameters_type: Type[SearchDocumentsParameters] = SearchDocumentsParameters
    response_type: Type[SearchDocumentsResponse] = SearchDocumentsResponse

    async def execute_graphql_query(self, gql_query: str, variables: dict):
        try:
            async with httpx.AsyncClient() as client:
                HASURA_ADMIN_SECRET = getenv("HASURA_ADMIN_SECRET")
                HASURA_POST_ENDPOINT = getenv("HASURA_POST_ENDPOINT")

                if HASURA_ADMIN_SECRET is None or HASURA_POST_ENDPOINT is None:
                    raise EnvironmentError("Missing necessary environment variables")
                HEADERS = {
                    "Content-Type": "application/json",
                    "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
                }
                response = await client.post(
                    HASURA_POST_ENDPOINT,
                    headers=HEADERS,
                    json={
                        "query": gql_query,
                        "variables": variables,
                    },
                )
                response.raise_for_status()
                response_json = response.json()

                if "errors" in response_json:
                    logger.error(f"GraphQL errors: {response_json['errors']}")
                    return None

                return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"Request failed with {e}")
            return None

        except Exception as generic_exc:
            logging.error(
                f"Unexpected error occurred while querying GraphQL: {generic_exc}"
            )
            return None

    async def fetch_documents(self, profile_id: int) -> str:
        """
        Fetches the documents for the given profile ID and concatenates their content.

        :param profile_id: The profile ID to fetch the documents for
        """
        query = """
        query getDocuments($ai_profile_id: bigint!) {
            ai_profiles(where: {id: {_eq: $ai_profile_id}}) {
                documents
            }
        }
        """
        variables = {"ai_profile_id": profile_id}
        try:
            response_json = await self.execute_graphql_query(query, variables)
            documents_data = response_json.get("data", {}).get("ai_profiles", [])
            documents = next(iter(documents_data), {}).get("documents", {})
            concatenated_content = ""
            for doc in documents.values():
                filename = doc.get("filename", "")
                content = doc.get("content", "")
                concatenated_content += f"{filename}\n{content}\n\n"
            return concatenated_content.strip()
        except Exception as e:
            logger.error(f"Failed to fetch documents: {str(e)}")
            return ""

    async def run(
        self, action_input: ActionInput[SearchDocumentsParameters]
    ) -> ActionOutput[SearchDocumentsResponse]:
        profile_id = action_input.action_config.ai_profile_id
        query = action_input.params.query
        documents_content = ""
        answer = ""
        try:
            documents_content = await self.fetch_documents(profile_id=profile_id)
            if documents_content:
                # Prepare the request data for the model
                requestData = {
                    "model": "gradientai/Llama-3-8B-Instruct-Gradient-1048k",
                    "messages": [
                        {"role": "system", "content": documents_content},
                        {
                            "role": "user",
                            "content": f"Based on the above context, please answer the following query: {query}",
                        },
                    ],
                    "max_tokens": 400,
                    "top_p": 0.9,
                    "temperature": 0.8,
                }
                # Send the request to the model
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        "https://azure5.ngrok.app/v1/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=requestData,
                    )
                    response.raise_for_status()
                    data = response.json()
                    logger.debug(f"Model response: {data}")
                    answer = data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("Error searching documents", exc_info=True)
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SearchDocumentsResponse(query=query, answer=answer),
        )
