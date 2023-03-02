from .base_agent import BaseAgent
from pydantic import BaseModel
import typing
from fastapi import APIRouter, WebSocket
from ..models.agent import AgentStartMessage, AgentReadyMessage, AgentTextMessage, WebSocketAgentMessage, WebSocketAgentMessageType
from jsonpath_ng import parse

class WebSocketAgent(BaseAgent):
        
    def __init__(self):
        super().__init__()
        self.app.websocket("/respond")(self.respond_websocket)

    async def respond_websocket(self, websocket: WebSocket):
        await websocket.accept()
        AgentStartMessage.parse_obj(await websocket.receive_json())
        await websocket.send_text(AgentReadyMessage().json())
        while True:
            message = WebSocketAgentMessage.parse_obj(await websocket.receive_json())
            if message.type == WebSocketAgentMessageType.AGENT_STOP:
                break
            text_message = typing.cast(AgentTextMessage, message)
            response = await self.respond(text_message.data.text)
            await websocket.send_text(AgentTextMessage.from_text(response).json())
        await websocket.close()

