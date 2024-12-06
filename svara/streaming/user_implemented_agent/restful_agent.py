# type: ignore
# to be deprecated

from typing import Union

from ..models.agent import RESTfulAgentEnd, RESTfulAgentInput, RESTfulAgentOutput, RESTfulAgentText
from .base_agent import BaseAgent


class RESTfulAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.app.post("/respond")(self.respond_rest)

    async def respond(self, human_input, conversation_id) -> RESTfulAgentOutput:
        raise NotImplementedError

    async def respond_rest(
        self, request: RESTfulAgentInput
    ) -> Union[RESTfulAgentText, RESTfulAgentEnd]:
        response = await self.respond(request.human_input, request.conversation_id)
        return response
