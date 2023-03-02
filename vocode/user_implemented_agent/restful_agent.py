from .base_agent import BaseAgent
from ..models.agent import RESTfulAgentInput, RESTfulAgentOutput
from pydantic import BaseModel
from fastapi import APIRouter

class RESTfulAgent(BaseAgent):
        
    def __init__(self):
        super().__init__()
        self.app.post("/respond")(self.respond_rest)

    async def respond_rest(self, request: RESTfulAgentInput) -> RESTfulAgentOutput:
        response = await self.respond(request.human_input)
        return RESTfulAgentOutput(response=response)

