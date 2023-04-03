import logging
from typing import Optional
import typing

from fastapi import APIRouter, WebSocket
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.websocket import (
    AudioMessage,
    ReadyMessage,
    WebSocketMessage,
    WebSocketMessageType,
)

from vocode.streaming.output_device.websocket_output_device import WebsocketOutputDevice
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber


class ConversationRouter:
    def __init__(
        self,
        transcriber: BaseTranscriber,
        agent: BaseAgent,
        synthesizer: BaseSynthesizer,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        self.transcriber = transcriber
        self.agent = agent
        self.synthesizer = synthesizer
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.router.websocket("/conversation")(self.conversation)

    def get_conversation(
        self, output_device: WebsocketOutputDevice
    ) -> StreamingConversation:
        return StreamingConversation(
            output_device, self.transcriber, self.agent, self.synthesizer, self.logger
        )

    async def conversation(self, websocket: WebSocket):
        await websocket.accept()
        self.logger.debug(f"Conversation started")
        output_device = WebsocketOutputDevice(websocket)
        conversation = self.get_conversation(output_device)
        await conversation.start(lambda: websocket.send_text(ReadyMessage().json()))
        while conversation.is_active():
            message: WebSocketMessage = WebSocketMessage.parse_obj(
                await websocket.receive_json()
            )
            if message.type == WebSocketMessageType.STOP:
                break
            audio_message = typing.cast(AudioMessage, message)
            conversation.receive_audio(audio_message.get_bytes())
        output_device.mark_closed()
        conversation.terminate()
