import logging
import httpx
import os

from vocode.streaming.models.call_type import CallType


HASURA_ADMIN_SECRET = os.getenv("HASURA_ADMIN_SECRET")
HASURA_POST_ENDPOINT = os.getenv("HASURA_POST_ENDPOINT")

HEADERS = {
    "Content-Type": "application/json",
    "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
}

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def get_transcripts(comms_id: int, table_name: str):
    query = f"""
    query getTranscript($id: bigint!) {{
      {table_name}(where: {{id: {{_eq: $id}}}}) {{
        machine_transcript
        transcript
      }}
    }}
    """
    variables = {
        "id": comms_id,
    }
    return await execute_graphql_query(query, variables)


async def update_comms_transcripts(
        comms_id: int,
        transcript_extension: str,
        table_name: str,
        machine_transcript_extension: str = "",
):
    # Fetch the current transcript
    current_transcript_result = await get_transcripts(comms_id, table_name)

    current_human_transcript = (
        current_transcript_result.get("data", {})
        .get(table_name, [{}])[0]
        .get("transcript", "")
    )
    current_machine_transcript = (
        current_transcript_result.get("data", {})
        .get(table_name, [{}])[0]
        .get("machine_transcript", "")
    )

    updated_human_transcript = (
        transcript_extension
        if not current_human_transcript
        else current_human_transcript + " " + transcript_extension
    )
    updated_machine_transcript = (
        machine_transcript_extension
        if not current_machine_transcript
        else current_machine_transcript + " " + machine_transcript_extension
    )

    mutation = f"""
    mutation updateTranscript($id: bigint!, $transcript: String, $machine_transcript: String) {{
      update_{table_name}(where: {{id: {{_eq: $id}}}}, _set: {{machine_transcript: $machine_transcript,
                                                                  transcript: $transcript}}) {{
        affected_rows
      }}
    }}
    """

    variables = {
        "id": comms_id,
        "machine_transcript": updated_machine_transcript,
        "transcript": updated_human_transcript,
    }
    return await execute_graphql_query(mutation, variables)


def get_current_calls_table(call_type: CallType):
    if call_type == CallType.OUTBOUND:
        return "calls"

    elif call_type == CallType.INBOUND:
        return "inbound_calls"

    elif call_type == CallType.UNDEFINED:
        raise ValueError(
            "We have a call type as UNDEFINED. Calls must be either set as INBOUND or OUTBOUND"
        )


async def update_call_transcripts(
        call_id: int,
        transcript_extension: str,
        call_type: CallType,
        machine_transcript_extension: str = "",
):
    # Fetch the current transcript
    current_table = get_current_calls_table(call_type)
    await update_comms_transcripts(
        comms_id=call_id,
        transcript_extension=transcript_extension,
        table_name=current_table,
        machine_transcript_extension=machine_transcript_extension,
    )


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
    mutation executeStatusUpdateByTelephonyId($telephony_id: String!, $status: String) {
      update_calls(
        where: {
          telephony_id: {
            _eq: $telephony_id
          }
        },
        _set: {
          status: $status
        }
      ) {
        affected_rows
      }
    }
    """
    variables = {
        "telephony_id": telephony_id,
        "status": call_status
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
