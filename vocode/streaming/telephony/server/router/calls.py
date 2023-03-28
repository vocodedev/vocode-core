from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, WebSocket
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)

from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.telephony.templates import Templater


class CallsRouter:
    def __init__(
        self,
        base_url: str,
        templater: Templater,
        config_manager: BaseConfigManager,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        self.base_url = base_url
        self.templater = templater
        self.config_manager = config_manager
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.router.websocket("/connect_call/{id}")(self.connect_call)

    async def connect_call(self, websocket: WebSocket, id: str):
        await websocket.accept()
        self.logger.debug("Phone WS connection opened for chat {}".format(id))
        call_config = self.config_manager.get_config(id)
        if not call_config:
            raise HTTPException(status_code=400, detail="No active phone call")

        call: Call = Call.from_call_config(
            self.base_url, call_config, self.config_manager, id, self.logger
        )

        await call.attach_ws_and_start(websocket)
        self.config_manager.delete_config(call.id)
        self.logger.debug("Phone WS connection closed for chat {}".format(id))

    def get_router(self) -> APIRouter:
        return self.router
