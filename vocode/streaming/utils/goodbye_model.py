import os
import asyncio
import requests
from typing import Optional

from openai import AsyncOpenAI
import numpy as np

from vocode import getenv

SIMILARITY_THRESHOLD = 0.9
EMBEDDING_SIZE = 1536
GOODBYE_PHRASES = [
    "bye",
    "goodbye",
    "see you",
    "see you later",
    "talk to you later",
    "talk to you soon",
    "have a good day",
    "have a good night",
]


class GoodbyeModel:
    def __init__(
        self,
        embeddings_cache_path=os.path.join(
            os.path.dirname(__file__), "goodbye_embeddings"
        ),
        openai_api_key: Optional[str] = None,
    ):
        self.async_openai_client = AsyncOpenAI(
            api_key=openai_api_key or getenv("OPENAI_API_KEY")
        )
        if not self.async_openai_client.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.embeddings_cache_path = embeddings_cache_path
        self.goodbye_embeddings: Optional[np.ndarray] = None

    async def initialize_embeddings(self):
        self.goodbye_embeddings = await self.load_or_create_embeddings(
            f"{self.embeddings_cache_path}/goodbye_embeddings.npy"
        )

    async def load_or_create_embeddings(self, path):
        if os.path.exists(path):
            return np.load(path)
        else:
            embeddings = await self.create_embeddings()
            np.save(path, embeddings)
            return embeddings

    async def create_embeddings(self):
        print("Creating embeddings...")
        size = EMBEDDING_SIZE
        embeddings = np.empty((size, len(GOODBYE_PHRASES)))
        for i, goodbye_phrase in enumerate(GOODBYE_PHRASES):
            embeddings[:, i] = await self.create_embedding(goodbye_phrase)
        return embeddings

    async def is_goodbye(self, text: str) -> bool:
        assert self.goodbye_embeddings is not None, "Embeddings not initialized"
        if "bye" in text.lower():
            return True
        embedding = await self.create_embedding(text.strip().lower())
        similarity_results = embedding @ self.goodbye_embeddings
        return np.max(similarity_results) > SIMILARITY_THRESHOLD

    async def create_embedding(self, text) -> np.ndarray:
        """
        Create an embedding for the given text using the OpenAI API.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector as a numpy array.
        """
        # Define the model to use
        model = getenv("AZURE_OPENAI_TEXT_EMBEDDING_ENGINE") or "text-embedding-ada-002"

        # Create the embedding using the OpenAI API
        response = await self.async_openai_client.embeddings.create(
            input=text, model=model
        )

        # # Extract the embedding data from the response
        embedding = np.array(response.data[0].embedding)

        return embedding


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        model = GoodbyeModel()
        while True:
            print(await model.is_goodbye(input("Text: ")))

    asyncio.run(main())
