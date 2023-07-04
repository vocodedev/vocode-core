import os
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.hosted.inbound_call_server import InboundCallServer
from vocode.streaming.models.agent import EchoAgentConfig

if __name__ == "__main__":
    server = InboundCallServer(
        agent_config=EchoAgentConfig(initial_message=BaseMessage(text="hello!")),
        twilio_config=TwilioConfig(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        ),
    )
    server.run(port=3002)
