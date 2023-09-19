import logging
import httpx
import os


HASURA_ADMIN_SECRET = os.getenv("HASURA_ADMIN_SECRET")
HASURA_POST_ENDPOINT = os.getenv("HASURA_POST_ENDPOINT")

HEADERS = {
    "Content-Type": "application/json",
    "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
}

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def get_transfer_conference_sid(telephony_id: str):
    query = """
    query getTransferConferenceSid($telephony_id: String!) {
      calls(where: { telephony_id: { _eq: $telephony_id } }) {
        transfer_conference_sid
      }
    }
    """
    variables = {
        "telephony_id": telephony_id
    }
    return await execute_graphql_query(query, variables)


# for legacy vocode reasons, telephony_call_sid (which we use in our code) is called telephony_id in vocode
# so, in our DB we also call it telephony_id; subject to change in the future
async def execute_status_update_by_telephony_id(telephony_id: str, call_status: str):
    mutation = """
    mutation executeStatusUpdateByTelephonyId($telephony_id: String!, $latest_status: String) {
      update_calls(
        where: {
          telephony_id: {
            _eq: $telephony_id
          }
        },
        _set: {
          latest_status: $latest_status
        }
      ) {
        affected_rows
      }
    }
    """
    variables = {
        "telephony_id": telephony_id,
        "latest_status": call_status
    }
    return await execute_graphql_query(mutation, variables)


async def execute_graphql_query(gql_query: str, variables: dict):
    try:
        async with httpx.AsyncClient() as client:
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

            if 'errors' in response_json:
                logger.error(f"GraphQL errors: {response_json['errors']}")
                return None

            return response_json
    except httpx.HTTPStatusError as e:
        logger.error(f"Request failed with {e}")
        return None
