from vocode.streaming.telephony.hosted.inbound_call_server import InboundCallServer
from vocode.streaming.models.agent import EchoAgentConfig

if __name__ == "__main__":
    server = InboundCallServer(agent_config=EchoAgentConfig(initial_message="hello!"))
    server.run(port=3001)
