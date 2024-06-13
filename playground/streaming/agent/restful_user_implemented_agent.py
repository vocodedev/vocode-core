# type: ignore

from typing import Generator, Optional, Tuple

from vocode.streaming.models.agent import RESTfulAgentOutput, RESTfulAgentText
from vocode.streaming.user_implemented_agent.restful_agent import RESTfulAgent


class EchoRESTfulAgent(RESTfulAgent):
    async def respond(self, human_input, conversation_id) -> RESTfulAgentOutput:
        return RESTfulAgentText(response=human_input)


EchoRESTfulAgent().run()
