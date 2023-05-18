# type: ignore
# to be deprecated

from .base_agent import BaseAgent
from ..models.agent import (
    RESTfulAgentInput,
    RESTfulAgentOutput,
    RESTfulAgentText,
    RESTfulAgentEnd,
)
from pydantic import BaseModel
from typing import Union
from fastapi import APIRouter


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
