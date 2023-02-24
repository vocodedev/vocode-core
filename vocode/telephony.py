import requests
from vocode.models.agent import InformationRetrievalAgentConfig, LLMAgentConfig
from vocode.models.telephony import CallEntity, CreateCallRequest
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("BASE_URL")


def create_call(request: CreateCallRequest):
    request_data = request.dict()

    url = f"http://{BASE_URL}/create_outbound_call"
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, json=request_data)
    return response.status_code


def create_information_retrieval_call(
    recipient: CallEntity,
    caller: CallEntity,
    goal_description: str,
    fields: list[str] = None,
):
    agent_config = InformationRetrievalAgentConfig(
        recipient_descriptor=recipient.descriptor,
        caller_descriptor=caller.descriptor,
        goal_description=goal_description,
        fields=fields,
    )

    return create_call(
        CreateCallRequest(
            recipient=recipient,
            caller=caller,
            agent_config=agent_config,
        )
    )
