from enum import Enum
from typing import Optional
from .model import TypedModel

DEFAULT_EMBEDDINGS_MODEL = "text-embedding-ada-002"


class VectorDBType(str, Enum):
    BASE = "vector_db_base"
    PINECONE = "vector_db_pinecone"


class VectorDBConfig(TypedModel, type=VectorDBType.BASE.value):
    embeddings_model: str = DEFAULT_EMBEDDINGS_MODEL


class PineconeConfig(VectorDBConfig, type=VectorDBType.PINECONE.value):
    index: str
    api_key: Optional[str]
    api_environment: Optional[str]
    top_k: int = 3
