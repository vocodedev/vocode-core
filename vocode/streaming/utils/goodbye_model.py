import os
import asyncio
import openai
from dotenv import load_dotenv
import numpy as np
import requests

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


PLATFORM = "pyq" if os.getenv("USE_PYQ_EMBEDDINGS", "false") == "true" else "openai"
SIMILARITY_THRESHOLD = 0.9
SIMILARITY_THRESHOLD_PYQ = 0.7
EMBEDDING_SIZE = 1536
PYQ_EMBEDDING_SIZE = 768
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
PYQ_API_URL = "https://embeddings.pyqai.com"


class GoodbyeModel:
    def __init__(
        self,
        embeddings_cache_path=os.path.join(
            os.path.dirname(__file__), "goodbye_embeddings"
        ),
    ):
        self.goodbye_embeddings = self.load_or_create_embeddings(
            f"{embeddings_cache_path}/goodbye_embeddings.npy"
        )
        self.goodbye_embeddings_pyq = self.load_or_create_embeddings(
            f"{embeddings_cache_path}/goodbye_embeddings_pyq.npy"
        )

    def load_or_create_embeddings(self, path):
        if os.path.exists(path):
            return np.load(path)
        else:
            embeddings = self.create_embeddings()
            np.save(path, embeddings)
            return embeddings

    def create_embeddings(self, platform=PLATFORM):
        print("Creating embeddings...")
        size = EMBEDDING_SIZE if platform == "openai" else PYQ_EMBEDDING_SIZE
        embeddings = np.empty((size, len(GOODBYE_PHRASES)))
        for i, goodbye_phrase in enumerate(GOODBYE_PHRASES):
            embeddings[:, i] = self.create_embedding(goodbye_phrase, platform=platform)
        return embeddings

    async def is_goodbye(self, text: str, platform=PLATFORM) -> bool:
        if "bye" in text.lower():
            return True
        embedding = self.create_embedding(text.strip().lower(), platform=platform)
        goodbye_embeddings = (
            self.goodbye_embeddings
            if platform == "openai"
            else self.goodbye_embeddings_pyq
        )
        threshold = (
            SIMILARITY_THRESHOLD if platform == "openai" else SIMILARITY_THRESHOLD_PYQ
        )
        similarity_results = embedding @ goodbye_embeddings
        return np.max(similarity_results) > threshold

    def create_embedding(self, text, platform=PLATFORM) -> np.array:
        if platform == "openai":
            return np.array(
                openai.Embedding.create(input=text, model="text-embedding-ada-002")[
                    "data"
                ][0]["embedding"]
            )
        elif platform == "pyq":
            return np.array(
                requests.post(
                    PYQ_API_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": os.getenv("PYQ_API_KEY"),
                    },
                    json={"input_sequence": [text], "account_id": "400"},
                ).json()["response"][0]
            )


if __name__ == "__main__":

    async def main():
        model = GoodbyeModel()
        while True:
            print(await model.is_goodbye(input("Text: ")))

    asyncio.run(main())
