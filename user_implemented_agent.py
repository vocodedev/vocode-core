from vocode.user_implemented_agent.restful_agent import RESTfulAgent
from vocode.models.agent import RESTfulAgentOutput, RESTfulAgentText, RESTfulAgentEnd, WebSocketAgentMessage, WebSocketAgentTextMessage, WebSocketAgentStopMessage
from vocode.user_implemented_agent.websocket_agent import WebSocketAgent 

class TestRESTfulAgent(RESTfulAgent):

    async def respond(self, input: str) -> RESTfulAgentOutput:
        print(input)
        if "bye" in input:
            return RESTfulAgentEnd()
        else:
            spelt = ''.join(i + j for i, j in zip(input, ' ' * len(input)))
            return RESTfulAgentText(response=spelt)
    
class TestWebSocketAgent(WebSocketAgent):

    async def respond(self, input: str) -> WebSocketAgentMessage:
        print(input)
        if "bye" in input:
            return WebSocketAgentStopMessage()
        else:
            spelt = ''.join(i + j for i, j in zip(input, ' ' * len(input)))
            return WebSocketAgentTextMessage.from_text(spelt)
        
if __name__ == "__main__":
    agent = TestWebSocketAgent()
    agent.run(port=3000)
