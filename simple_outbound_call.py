from vocode.telephony.outbound_call import OutboundCall
from vocode.models.telephony import CallEntity
from vocode.models.agent import EchoAgentConfig, WebSocketUserImplementedAgentConfig

if __name__ == '__main__':
    call = OutboundCall(
        recipient=CallEntity(
            phone_number="+11234567890",
        ),
        caller=CallEntity(
            phone_number="+11234567890",
        ),
        agent_config=EchoAgentConfig(initial_message="Hello!")
    )
    call.start()
