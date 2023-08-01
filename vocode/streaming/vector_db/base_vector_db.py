from typing import Optional
import aiohttp


class VectorDB:
    def __init__(self, aiohttp_session: Optional[aiohttp.ClientSession] = None,):
        if aiohttp_session:
            # the caller is responsible for closing the session
            self.aiohttp_session = aiohttp_session
        else:
            self.aiohttp_session = aiohttp.ClientSession()

    async def add_texts(self):
        raise NotImplementedError

    async def similarity_search_with_score(self):
        raise NotImplementedError
