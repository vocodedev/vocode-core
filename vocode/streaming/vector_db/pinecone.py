import logging
from typing import Iterable, List, Optional, Tuple
import uuid
from langchain.docstore.document import Document
from vocode import getenv
from vocode.streaming.models.vector_db import PineconeConfig
from vocode.streaming.vector_db.base_vector_db import VectorDB

logger = logging.getLogger(__name__)


class PineconeDB(VectorDB):
    def __init__(self, config: PineconeConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config

        self.index_name = self.config.index
        self.pinecone_api_key = getenv("PINECONE_API_KEY") or self.config.api_key
        self.pinecone_environment = (
            getenv("PINECONE_ENVIRONMENT") or self.config.api_environment
        )
        self.pinecone_url = (
            f"https://{self.index_name}.svc.{self.pinecone_environment}.pinecone.io"
        )
        self._text_key = "text"

    async def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        namespace: Optional[str] = None,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            ids: Optional list of ids to associate with the texts.
            namespace: Optional pinecone namespace to add the texts to.

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        # Adapted from: langchain/vectorstores/pinecone.py. Made langchain implementation async.
        if namespace is None:
            namespace = ""
        # Embed and create the documents
        docs = []
        ids = ids or [str(uuid.uuid4()) for _ in texts]
        for i, text in enumerate(texts):
            embedding = await self.create_openai_embedding(text)
            metadata = metadatas[i] if metadatas else {}
            metadata[self._text_key] = text
            docs.append({"id": ids[i], "values": embedding, "metadata": metadata})
        # upsert to Pinecone
        async with self.aiohttp_session.post(
            f"{self.pinecone_url}/vectors/upsert",
            headers={"Api-Key": self.pinecone_api_key},
            json={
                "vectors": docs,
                "namespace": namespace,
            },
        ) as response:
            response_json = await response.json()
            if "message" in response_json:
                logger.error(f"Error upserting vectors: {response_json}")

        return ids

    async def similarity_search_with_score(
        self,
        query: str,
        filter: Optional[dict] = None,
        namespace: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        """Return pinecone documents most similar to query, along with scores.

        Args:
            query: Text to look up documents similar to.
            filter: Dictionary of argument(s) to filter on metadata
            namespace: Namespace to search in. Default will search in '' namespace.

        Returns:
            List of Documents most similar to the query and score for each
        """
        # Adapted from: langchain/vectorstores/pinecone.py. Made langchain implementation async.
        if namespace is None:
            namespace = ""
        query_obj = await self.create_openai_embedding(query)
        docs = []
        async with self.aiohttp_session.post(
            f"{self.pinecone_url}/query",
            headers={"Api-Key": self.pinecone_api_key},
            json={
                "top_k": self.config.top_k,
                "namespace": namespace,
                "filter": filter,
                "vector": query_obj,
                "includeMetadata": True,
            },
        ) as response:
            results = await response.json()

        for res in results["matches"]:
            metadata = res["metadata"]
            if self._text_key in metadata:
                text = metadata.pop(self._text_key)
                score = res["score"]
                docs.append((Document(page_content=text, metadata=metadata), score))
            else:
                logger.warning(
                    f"Found document with no `{self._text_key}` key. Skipping."
                )
        return docs
