import logging
from typing import Iterable, List, Optional, Tuple
import uuid
from langchain.docstore.document import Document
from vocode import getenv
from vocode.streaming.models.vector_db import QdrantConfig
from vocode.streaming.vector_db.base_vector_db import VectorDB
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QdrantDB(VectorDB):
    def __init__(self, config: QdrantConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.collection_name = self.config.index
        self.top_k = self.config.top_k or 1
        self.client = QdrantClient('localhost', port=6333)
        self._text_key = "text"
       
    async def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        points = []
        for i, text in enumerate(texts):
            embedding = await self.create_openai_embedding(text)
            metadata = metadatas[i] if metadatas else {}
            metadata[self._text_key] = text
            points.append(PointStruct(id=ids[i], vector=embedding, payload=metadata))

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                wait=True,
                points=points
            )
        except Exception as e:
            logger.error(f"Error upserting points: {e}")

        return ids

    async def similarity_search_with_score(
        self,
        query: str,
        filter: Optional[dict] = None,
    ) -> List[Tuple[Document, float]]:
        query_vector = await self.create_openai_embedding(query)
        qdrant_filter = None
        if filter:
            qdrant_filter = Filter(must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()])

        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                with_payload=True,
                limit=self.config.top_k
            )
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []

        docs = []
        for res in search_result:
            payload = res.payload
            metadata = payload.get("metadata", {})
            content = payload.get("content", "")
            score = res.score
            
            docs.append((Document(page_content=content.replace(r"\n","\n"), metadata=metadata), score))

        return docs

