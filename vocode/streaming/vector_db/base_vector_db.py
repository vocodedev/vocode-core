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

        if openai.api_type and "azure" in openai.api_type:
            self.openai_async_client = openai.AsyncAzureOpenAI(
                azure_endpoint = os.getenv("AZURE_OPENAI_API_BASE"),
                api_key = os.getenv("AZURE_OPENAI_API_KEY"),
                api_version = "2023-05-15"
            )
        else:
            self.openai_async_client = openai.AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )

    async def create_openai_embedding(
        self, text, model=DEFAULT_OPENAI_EMBEDDING_MODEL
    ) -> List[float]:
        params = {
            "input": text,
            "model": "text-embedding-ada-002",
        }

        response = await self.openai_async_client.embeddings.create(**params)
        return list(response.model_dump_json(indent=2))

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
