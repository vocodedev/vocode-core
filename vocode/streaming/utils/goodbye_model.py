import asyncio
import os
from typing import Optional

from vocode.streaming.utils.embedding_model import EmbeddingModel

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


class GoodbyeModel(EmbeddingModel):
    def __init__(self, embeddings_cache_path=os.path.join(
        os.path.dirname(__file__), "goodbye_embeddings"
    ), embeddings_file: str = 'goodbye_embeddings', openai_api_key: Optional[str] = None):
        self.phrases = GOODBYE_PHRASES
        self.strict_phrases = ["bye"]
        super().__init__(embeddings_cache_path, embeddings_file, openai_api_key)

    async def is_goodbye(self, text: str) -> bool:
        return await self.is_similar(text)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()


    async def main():
        model = GoodbyeModel()
        while True:
            print(await model.is_goodbye(input("Text: ")))


    asyncio.run(main())
