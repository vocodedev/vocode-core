from fastapi import FastAPI, APIRouter
import uvicorn

class BaseAgent():

    def __init__(self):
        self.app = FastAPI()

    async def respond(self, human_input) -> str:
        raise NotImplementedError
    
    def run(self, host="localhost", port=3001):
        uvicorn.run(self.app, host=host, port=port)