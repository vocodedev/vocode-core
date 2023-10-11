from typing import Optional

from vocode.streaming.utils.embedding_model import EmbeddingModel

FillerPhrases = [
    "Hmm",
    "I see",
    "Interesting",
    "Go on",
    "That's a good point",
    "I'm listening",
    "Tell me more",
    "Oh, really",
    "Fascinating",
    "I'm with you",
    "I understand",
    "Please continue",
    "Interesting, go on",
    "I'm following you",
    "Mm-hmm",
    "I'm intrigued"
]


class FillerModel(EmbeddingModel):
    def __init__(self, embeddings_cache_path: str = "filler_embeddings", embeddings_file: str = 'filler_embeddings',
                 openai_api_key: Optional[str] = None):
        self.phrases = FillerPhrases
        self.strict_phrases = ["hmm", 'go on', "tell me more", "please continue"]
        super().__init__(embeddings_cache_path, embeddings_file, openai_api_key)

    async def is_filler(self, text: str) -> bool:
        return await self.is_similar(text)
