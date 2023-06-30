import os
import asyncio
from functools import partial
from langchain.vectorstores import Pinecone
from vocode.streaming.models.vector_db import PineconeConfig
from langchain.embeddings.openai import OpenAIEmbeddings
from vocode.streaming.vector_db.base_vector_db import VectorDB


class PineconeDB(VectorDB):
    def __init__(self, config: PineconeConfig) -> None:
        import pinecone

        self.config = config
        self.pinecone = pinecone

        pinecone.init(
            api_key=os.environ["PINECONE_API_KEY"],
            environment=os.environ["PINECONE_ENVIRONMENT"],
        )
        index = self.pinecone.Index(self.config.index)
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = Pinecone(index, self.embeddings.embed_query, "text")

    async def add_texts(self, texts, **kwargs):
        func = partial(self.vectorstore.add_texts, texts, **kwargs)
        return await asyncio.get_event_loop().run_in_executor(None, func)

    async def similarity_search_with_score(self, query, k=4, **kwargs):
        func = partial(
            self.vectorstore.similarity_search_with_score, query, k, **kwargs
        )
        return await asyncio.get_event_loop().run_in_executor(None, func)
