from ..models.telephony import CallEntity, CreateOutboundCall
import requests
from .. import api_key, BASE_URL

VOCODE_OUTBOUND_CALL_URL = f"https://{BASE_URL}/create_outbound_call"

class OutboundCall:

    def __init__(self, recipient: CallEntity, caller: CallEntity, agent_config):
        self.recipient = recipient
        self.caller = caller
        self.agent_config = agent_config

    def start(self):
        return requests.post(
            VOCODE_OUTBOUND_CALL_URL,
            headers={
                "Authorization": f"Bearer {api_key}"
            },
            json=CreateOutboundCall(
                recipient=self.recipient,
                caller=self.caller,
                agent_config=self.agent_config
            ).dict()
        )

    