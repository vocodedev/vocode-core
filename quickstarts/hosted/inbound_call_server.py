import os
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.telephony.hosted.inbound_call_server import InboundCallServer
from vocode.streaming.models.agent import EchoAgentConfig

if __name__ == "__main__":
    server = InboundCallServer(
        agent_config=EchoAgentConfig(initial_message=BaseMessage(text="hello!")),
        vonage_config=VonageConfig(
            api_key=os.environ["VONAGE_API_KEY"],
            api_secret=os.environ["VONAGE_API_SECRET"],
            application_id=os.environ["VONAGE_APPLICATION_ID"],
            private_key=os.environ["VONAGE_PRIVATE_KEY"],
        ),
    )
    server.run(port=3002)
