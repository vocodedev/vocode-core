from vocode.user_implemented_agent.restful_agent import RESTfulAgent
from vocode.user_implemented_agent.websocket_agent import WebSocketAgent 

class EchoAgent(WebSocketAgent):

    async def respond(self, input: str) -> str:
        print(input)
        return ''.join(i + j for i, j in zip(input, ' ' * len(input)))
    
if __name__ == "__main__":
    agent = EchoAgent()
    agent.run()
