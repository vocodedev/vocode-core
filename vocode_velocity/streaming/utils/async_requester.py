from typing import Optional

import aiohttp
import httpx
from aiohttp import BaseConnector
from pydantic import BaseModel

from vocode.streaming.utils.singleton import Singleton


class AsyncRequestor(Singleton):
    def __init__(self, connector: Optional[BaseConnector] = None):
        self.session = aiohttp.ClientSession(connector=connector)
        self.async_client = httpx.AsyncClient()
        self.connector = connector

    def get_session(self):
        if self.session.closed:
            self.session = aiohttp.ClientSession(connector=self.connector)
        return self.session

    def get_client(self):
        return self.async_client

    async def close_session(self):
        if not self.session.closed:
            await self.session.close()

    async def close_client(self):
        await self.async_client.aclose()
