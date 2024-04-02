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


class RetrieveInstructionsActionConfig(
    ActionConfig, type=ActionType.RETRIEVE_INSTRUCTIONS
):
    pass


class RetrieveInstructionsParameters(BaseModel):
    id: int = Field(..., description="The agent ID to fetch the profile for")


class RetrieveInstructionsResponse(BaseModel):
    agent_profile: dict = Field(
        None, description="The agent profile fetched from the database"
    )


class RetrieveInstructions(
    BaseAction[
        RetrieveInstructionsActionConfig,
        RetrieveInstructionsParameters,
        RetrieveInstructionsResponse,
    ]
):
    description: str = "Retrievees the instructions based on the agent profile"
    parameters_type: Type[RetrieveInstructionsParameters] = (
        RetrieveInstructionsParameters
    )
    response_type: Type[RetrieveInstructionsResponse] = RetrieveInstructionsResponse

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

    async def fetch_agent_profile(self, agent_id: int) -> dict:
        """
        Fetches the agent profile for the given agent ID.

        :param agent_id: The agent ID to fetch the profile for
        """
        query = f"""
        query getInitialSystemMessages($ai_profile_id: bigint!) {{
            ai_profiles(where: {{id: {{_eq: $ai_profile_id}}}}) {{
                user_plaintext_prompt
                generated_json
                base_message
                data_injection_func
                voice_id
                transcript_analyzer_func
                language
                gender
                model_name
                use_filler_words
            }}
        }}
    """
        variables = {
            "ai_profile_id": agent_id
        }  # Corrected variable name to match the GraphQL query parameter
        try:
            response_json = await self.execute_graphql_query(query, variables)
            agent_profiles_data = response_json.get("data", {}).get("ai_profiles", [])
            return next(iter(agent_profiles_data), {})
        except Exception as e:
            logger.error(f"Failed to fetch agent profile: {str(e)}")
            return {}

    async def run(
        self, action_input: ActionInput[RetrieveInstructionsParameters]
    ) -> ActionOutput[RetrieveInstructionsResponse]:
        agent_id = action_input.params.id
        try:
            agent_profile = await self.fetch_agent_profile(agent_id=agent_id)
        except Exception as e:
            agent_profile = None
            logger.error(f"Error fetching agent profile: {str(e)}")
        if agent_profile:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=RetrieveInstructionsResponse(agent_profile=agent_profile),
            )
        else:
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=RetrieveInstructionsResponse(
                    agent_profile={"ERROR": "Error fetching instructions."}
                ),
            )
