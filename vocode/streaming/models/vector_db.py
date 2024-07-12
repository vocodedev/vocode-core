from abc import ABC
from enum import Enum
from typing import Any, Literal, Optional

from vocode.streaming.models.adaptive_object import AdaptiveObject

DEFAULT_EMBEDDINGS_MODEL = "text-embedding-ada-002"


class VectorDBConfig(AdaptiveObject, ABC):
    type: Any
    embeddings_model: str = DEFAULT_EMBEDDINGS_MODEL


class PineconeConfig(VectorDBConfig):
    type: Literal["vector_db_pinecone"] = "vector_db_pinecone"
    index: str
    api_key: Optional[str]
    api_environment: Optional[str]
    top_k: int = 3
