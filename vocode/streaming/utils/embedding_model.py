import logging
import os
from typing import List, Optional

import numpy as np
import openai

from vocode import getenv

SIMILARITY_THRESHOLD = 0.9
EMBEDDING_SIZE = 1536


class EmbeddingModel:
    phrases: List[str] = []
    strict_phrases: List[str] = []

    def __init__(self, embeddings_cache_path: str, embeddings_file: str, openai_api_key: Optional[str] = None,
                 logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.embeddings: Optional[np.ndarray] = None
        self.embeddings_cache_path = embeddings_cache_path
        openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.embeddings_file = embeddings_file

    async def load_or_create_embeddings(self, path):
        if os.path.exists(path):
            return np.load(path)
        else:
            embeddings = await self.create_embeddings()
            np.save(path, embeddings)
            return embeddings

    async def initialize_embeddings(self):
        self.embeddings = await self.load_or_create_embeddings(
            f"{self.embeddings_cache_path}/{self.embeddings_file}.npy"
        )

    async def create_embeddings(self):
        self.logger.debug(f"creating embeddings for {self.__class__.__name__}")
        size = EMBEDDING_SIZE
        embeddings = np.empty((size, len(self.phrases)))
        for i, goodbye_phrase in enumerate(self.phrases):
            embeddings[:, i] = await self.create_embedding(goodbye_phrase)
        return embeddings

    async def is_similar(self, text):
        assert self.embeddings is not None, "Embeddings not initialized"
        text_lower = text.lower()
        for phrase in self.strict_phrases:
            if phrase in text_lower:
                return True
        embedding = await self.create_embedding(text.strip().lower())
        similarity_results = embedding @ self.embeddings
        return np.max(similarity_results) > SIMILARITY_THRESHOLD

    async def create_embedding(self, text) -> np.ndarray:
        params = {
            "input": text,
        }

        engine = getenv("AZURE_OPENAI_TEXT_EMBEDDING_ENGINE")
        if engine:
            params["engine"] = engine
        else:
            params["model"] = "text-embedding-ada-002"

        return np.array(
            (await openai.Embedding.acreate(**params))["data"][0]["embedding"]
        )
