from typing import Optional
import aiohttp


class VectorDB:
    def __init__(self, aiohttp_session: Optional[aiohttp.ClientSession] = None,):
        if aiohttp_session:
            # the caller is responsible for closing the session
            self.aiohttp_session = aiohttp_session
            self.should_close_session_on_tear_down = False
        else:
            self.aiohttp_session = aiohttp.ClientSession()
            self.should_close_session_on_tear_down = True

    async def add_texts(self):
        raise NotImplementedError

    async def similarity_search_with_score(self):
        raise NotImplementedError
    
    async def tear_down(self):
        if self.should_close_session_on_tear_down:
            await self.aiohttp_session.close()
