import aiohttp
import httpx

from vocode.streaming.utils.singleton import Singleton


class AsyncRequestor(Singleton):
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.async_client = httpx.AsyncClient()

    def get_session(self):
        if self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def get_client(self):
        return self.async_client

    async def close_session(self):
        if not self.session.closed:
            await self.session.close()

    async def close_client(self):
        await self.async_client.aclose()
