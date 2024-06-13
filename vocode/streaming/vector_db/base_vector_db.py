import os
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

import aiohttp
from openai import AsyncAzureOpenAI, AsyncOpenAI

from vocode.streaming.models.agent import AZURE_OPENAI_DEFAULT_API_VERSION

if TYPE_CHECKING:
    from langchain.docstore.document import Document

DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"


class VectorDB:
    openai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]

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

        self.engine = os.getenv("AZURE_OPENAI_TEXT_EMBEDDING_ENGINE")
        if self.engine:
            azure_base = os.getenv("AZURE_OPENAI_API_BASE_EAST_US")
            azure_base = azure_base if azure_base is not None else ""
            self.openai_client = AsyncAzureOpenAI(
                azure_endpoint=azure_base,
                api_key=os.getenv("AZURE_OPENAI_API_KEY_EAST_US"),
                api_version=AZURE_OPENAI_DEFAULT_API_VERSION,
            )
        else:
            self.openai_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
            )

    async def create_openai_embedding(
        self, text, model=DEFAULT_OPENAI_EMBEDDING_MODEL
    ) -> List[float]:
        params = {
            "input": text,
        }

        params["model"] = self.engine if self.engine else model

        return (await self.openai_client.embeddings.create(**params)).data[0].embedding

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
    ) -> List[Tuple["Document", float]]:
        raise NotImplementedError

    async def tear_down(self):
        if self.should_close_session_on_tear_down:
            await self.aiohttp_session.close()
