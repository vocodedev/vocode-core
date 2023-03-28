from typing import AsyncGenerator
from vocode.streaming.user_implemented_agent.restful_agent import RESTfulAgent
from vocode.streaming.models.agent import (
    RESTfulAgentOutput,
    RESTfulAgentText,
    RESTfulAgentEnd,
    WebSocketAgentMessage,
    WebSocketAgentTextEndMessage,
    WebSocketAgentTextMessage,
    WebSocketAgentStopMessage,
)
from vocode.streaming.user_implemented_agent.websocket_agent import WebSocketAgent


class TestRESTfulAgent(RESTfulAgent):
    async def respond(self, input: str, conversation_id: str) -> RESTfulAgentOutput:
        print(input, conversation_id)
        if "bye" in input:
            return RESTfulAgentEnd()
        else:
            spelt = "".join(i + j for i, j in zip(input, " " * len(input)))
            return RESTfulAgentText(response=spelt)


class TestWebSocketAgent(WebSocketAgent):
    async def respond(self, input: str, conversation_id: str) -> WebSocketAgentMessage:
        print(input, conversation_id)
        if "bye" in input:
            return WebSocketAgentStopMessage()
        else:
            spelt = "".join(i + j for i, j in zip(input, " " * len(input)))
            return WebSocketAgentTextMessage.from_text(spelt)

    async def generate_response(
        self, input: str, conversation_id: str
    ) -> AsyncGenerator[WebSocketAgentMessage, None]:
        print(input, conversation_id)
        if "bye" in input:
            yield WebSocketAgentTextEndMessage()
        else:
            for word in input.split():
                yield WebSocketAgentTextMessage.from_text(word)
            yield WebSocketAgentTextEndMessage()


if __name__ == "__main__":
    agent = TestWebSocketAgent(generate_responses=True)
    agent.run(port=3001)
