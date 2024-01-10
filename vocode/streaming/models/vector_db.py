from enum import Enum
from typing import Optional, Callable
from .model import TypedModel

DEFAULT_EMBEDDINGS_MODEL = "text-embedding-ada-002"


class VectorDBType(str, Enum):
    BASE = "vector_db_base"
    PINECONE = "vector_db_pinecone"
    CHROMA = "vector_db_chroma"

class VectorDBConfig(TypedModel, type=VectorDBType.BASE.value):
    embeddings_model: str = DEFAULT_EMBEDDINGS_MODEL


class PineconeConfig(VectorDBConfig, type=VectorDBType.PINECONE.value):
    index: str
    api_key: Optional[str]
    api_environment: Optional[str]
    top_k: int = 3

class ChromaDBConfig(VectorDBConfig, type=VectorDBType.CHROMA.value):
    collection: str
    host: str
    port: Optional[str]
    api_key: Optional[str]
    top_k: int = 3
    embeddings_function: Optional[Callable] = None # default is OpenAIEmbeddingFunction