import logging
from typing import Iterable, List, Optional, Tuple
import uuid
from langchain.docstore.document import Document
from vocode import getenv
from vocode.streaming.models.vector_db import ChromaDBConfig
from vocode.streaming.vector_db.base_vector_db import VectorDB
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1536

class ChromaDB(VectorDB):

    """VectorDB implementation using ChromaDB."""

    def __init__(self, config: ChromaDBConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.collection_name = self.config.collection
        self.chroma_api_key = self.config.api_key or getenv("CHROMA_API_KEY")
        self.port = config.port or getenv("CHROMA_SERVER_HTTP_PORT", "8000")
        self.host = config.host or getenv("CHROMA_SERVER_HOST", "localhost")

        self.client = chromadb.HttpClient(
            host=self.host, 
            port=self.port,
            headers={
                "X-Chroma-Token": f"{self.chroma_api_key}"
            }
        )
        self.collection = self.client.get_collection(
            name=self.collection_name,
            embedding_function=self.config.embeddings_function or self._default_embedding_fn(),
        )

        self._text_key = "text"

    def _default_embedding_fn(self):
        OPENAI_API_KEY = getenv("OPENAI_API_KEY")
        default_embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=self.config.embeddings_model # should be "text-embedding-ada-002"
        )
        return default_embedding_fn

    def _create_AND_eq_filter(self, input_data: dict) -> dict:
        and_query = {"$and": []}

        for key, value in input_data.items():
            condition = {key: {"$eq": value}}
            and_query["$and"].append(condition)

        return and_query

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
        raise NotImplementedError
        self.collection.add(
            ids=ids or [str(uuid.uuid4()) for _ in texts],
            documents=texts,
            metadatas=metadatas
        )
        raise NotImplementedError

    async def similarity_search_with_score(
        self,
        query: str,
        filter: Optional[dict] = None,
        namespace: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        """Return documents most similar to query, along with scores.

        Args:
            query: Text to look up documents similar to.
            filter: Dictionary of argument(s) to filter on metadata
            include: List of what to include in the response. Default is ["metadatas", "distances"].
            namespace: Namespace to search in. Default will search in '' namespace.

        Returns:
            List of Documents most similar to the query and score for each
        """
        docs = []
        filters = self._create_AND_eq_filter(input_data=filter) if filter else None
        results = self.collection.query(
            query_texts=[query],
            n_results=self.config.top_k,
            include=["metadatas", "distances"],
            where=filters,
        )

        metadatas = results["metadatas"]
        distances = results["distances"]

        if metadatas is None or distances is None:
            return docs
        
        metadatas_and_distances = zip(metadatas[0], distances[0])
        for item in metadatas_and_distances:
            metadata: dict = item[0]
            dist: float = item[1]
            if self._text_key in metadata:
                text = metadata.pop(self._text_key)
                similarity = 1 - dist
                docs.append((
                    Document(
                        page_content=text, 
                        metadata=metadata
                    ),
                    similarity)
                )
            else:
                logger.warning(
                    f"Found document with no `{self._text_key}` key. Skipping."
                )
        return docs
    
    async def retrieve_k_vectors_with_filter(
        self,
        filters: Optional[dict] = None,
        k: Optional[int] = 50,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        """Return pinecone list of documents based on filter.

        Args:
            filters: Dictionary of argument(s) to filter on metadata
            k: Int of number of vectors to retrieve. Default is 500.
            include: List of what to include in the response. Default is ["metadatas", "distances"].

        Returns:
            List of Documents where each document is a vector and metadata.
        """
        query_embedding = [1] + [0] * (EMBEDDING_DIMENSION - 1)
        logger.debug(f"filters: {filters}")
        assert isinstance(filters, dict)
        logger.debug(f"type(filters): {type(filters)}")
        docs = []
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["metadatas", "documents", "distances"],
            where=self._create_AND_eq_filter(filters) if filters else None,
        )

        metadatas = results["metadatas"]

        if metadatas is None or len(metadatas[0]) == 0:
            return docs
        
        metadatas: List[dict] = metadatas[0]
        for metadata in metadatas:
            if self._text_key in metadata:
                text = metadata.pop(self._text_key)
                docs.append(Document(page_content=text, metadata=metadata))
            else:
                logger.warning(
                    f"Found document with no `{self._text_key}` key. Skipping."
                )
        return docs