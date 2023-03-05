from .base_agent import BaseAgent
import uuid
import typing
from typing import Union, Optional
from fastapi import WebSocket
from ..models.agent import (
    WebSocketAgentStartMessage, 
    WebSocketAgentReadyMessage, 
    WebSocketAgentTextMessage, 
    WebSocketAgentStopMessage, 
    WebSocketAgentMessage, 
    WebSocketAgentMessageType
)

class WebSocketAgent(BaseAgent):
        
    def __init__(self):
        super().__init__()
        self.app.websocket("/respond")(self.respond_websocket)

    async def respond(self, human_input: str, conversation_id: Optional[str] = None) -> Union[WebSocketAgentTextMessage, WebSocketAgentStopMessage]:
        raise NotImplementedError

    async def respond_websocket(self, websocket: WebSocket):
        await websocket.accept()
        conversation_id = str(uuid.uuid4())
        WebSocketAgentStartMessage.parse_obj(await websocket.receive_json())
        await websocket.send_text(WebSocketAgentReadyMessage().json())
        while True:
            input_message = WebSocketAgentMessage.parse_obj(await websocket.receive_json())
            if input_message.type == WebSocketAgentMessageType.STOP:
                break
            text_message = typing.cast(WebSocketAgentTextMessage, input_message)
            output_response = await self.respond(text_message.data.text, conversation_id=conversation_id)
            await websocket.send_text(output_response.json())
        await websocket.close()

