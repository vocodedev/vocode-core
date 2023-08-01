import os
from typing import Iterable, List, Optional, Tuple
import aiohttp
import openai
from langchain.docstore.document import Document

DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"


class VectorDB:
    def __init__(
        self,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        if aiohttp_session:
            # the caller is responsible for closing the session
            self.aiohttp_session = aiohttp_session
            self.should_close_session_on_tear_down = False
        else:
            self.aiohttp_session = aiohttp.ClientSession()
            self.should_close_session_on_tear_down = True

    async def create_openai_embedding(
        self, text, model=DEFAULT_OPENAI_EMBEDDING_MODEL
    ) -> List[float]:
        params = {
            "input": text,
        }

        engine = os.getenv("AZURE_OPENAI_TEXT_EMBEDDING_ENGINE")
        if engine:
            params["engine"] = engine
        else:
            params["model"] = model

        return list((await openai.Embedding.acreate(**params))["data"][0]["embedding"])

    async def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        namespace: Optional[str] = None,
    ) -> List[str]:
        raise NotImplementedError

    async def similarity_search_with_score(
        self,
        query: str,
        filter: Optional[dict] = None,
        namespace: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        raise NotImplementedError

    async def tear_down(self):
        if self.should_close_session_on_tear_down:
            await self.aiohttp_session.close()
