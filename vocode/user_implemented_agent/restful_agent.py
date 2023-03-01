from .base_agent import BaseAgent
from pydantic import BaseModel
from fastapi import APIRouter

class RESTfulAgent(BaseAgent):

    class HumanInput(BaseModel):
        human_input: str
        
    def __init__(self):
        super().__init__()
        self.app.post("/respond")(self.respond_rest)

    async def respond_rest(self, request: HumanInput):
        response = await self.respond(request.human_input)
        return {"response": response}

