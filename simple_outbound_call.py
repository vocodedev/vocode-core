from vocode.outbound_call import OutboundCall
from vocode.models.telephony import CallEntity
from vocode.models.agent import EchoAgentConfig, WebSocketUserImplementedAgentConfig

if __name__ == '__main__':
    call = OutboundCall(
        recipient=CallEntity(
            phone_number="+14088926228",
        ),
        caller=CallEntity(
            phone_number="+14086600744",
        ),
        agent_config=WebSocketUserImplementedAgentConfig(
            respond=WebSocketUserImplementedAgentConfig.RouteConfig(
                url="ws://localhost:3001/respond"
            )
        )
    )
    call.start()