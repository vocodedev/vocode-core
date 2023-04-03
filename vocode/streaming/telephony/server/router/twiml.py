import logging
from typing import Optional

from fastapi import APIRouter

from vocode.streaming.telephony.templates import Templater
from vocode.streaming.utils.base_router import BaseRouter


class TwiMLRouter(BaseRouter):
    def __init__(
        self,
        base_url: str,
        templater: Templater,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        self.base_url = base_url
        self.templater = templater
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.router.add_api_route(
            "/twiml/initiate_call/{id}", self.call_twiml, methods=["POST"]
        )

    def call_twiml(self, id: str):
        return self.templater.get_connection_twiml(base_url=self.base_url, call_id=id)

    def get_router(self) -> APIRouter:
        return self.router
