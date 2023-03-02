from vocode.user_implemented_agent.restful_agent import RESTfulAgent
from vocode.user_implemented_agent.websocket_agent import WebSocketAgent 

class EchoAgent(RESTfulAgent):

    async def respond(self, input: str) -> str:
        return input
    
if __name__ == "__main__":
    agent = EchoAgent()
    agent.run()