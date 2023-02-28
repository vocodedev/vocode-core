import logging
import requests
from vocode.models.agent import InformationRetrievalAgentConfig, LLMAgentConfig
from vocode.models.telephony import CallEntity, CreateCallRequest
from . import api_key

BASE_URL = "https://0a7e-136-24-82-111.ngrok.io"


class Telephony:
    def __init__(self, logger: logging.Logger = None) -> None:
        self.logger = logger

    def create_call(self, request: CreateCallRequest):
        request_data = request.dict()

        url = f"{BASE_URL}/create_outbound_call?key={api_key}"
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, json=request_data)
        return response.status_code

    def create_information_retrieval_call(
        self,
        recipient: CallEntity,
        caller: CallEntity,
        goal_description: str,
        fields: list[str] = [],
    ):
        agent_config = InformationRetrievalAgentConfig(
            recipient_descriptor=recipient.descriptor,
            caller_descriptor=caller.descriptor,
            goal_description=goal_description,
            fields=fields,
        )

        return self.create_call(
            CreateCallRequest(
                recipient=recipient,
                caller=caller,
                agent_config=agent_config,
            )
        )
