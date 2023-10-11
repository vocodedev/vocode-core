import os
from typing import Optional

from vocode.streaming.utils.embedding_model import EmbeddingModel

SIMILARITY_THRESHOLD = 0.9
EMBEDDING_SIZE = 1536
INTERRUPT_PHRASES = [
    "wait",
    "hold on",
    "hold up",
    "one second",
    "one moment",
    "just a second",
    "just a moment",
    "just a minute",
    "just a sec",
    "Excuse me, but",
    "I'm sorry to interrupt, but",
    "Can I jump in here for a moment",
    "May I interject something",
    "If I may add",
    "Pardon me, but I'd like to say",
    "Just a quick point",
    "Hang on a sec, I have something to say",
    "Wait, let me stop you there",
    "Before you continue, I wanted to mention",
    "I hate to cut you off, but",
    "I'd like to chime in",
    "Can I offer my perspective",
    "I'd like to share my thoughts on this",
    "Sorry, but I think",
    "Let me quickly mention"
]


class InterruptModel(EmbeddingModel):
    def __init__(self, embeddings_cache_path=os.path.join(os.path.dirname(__file__), "interrupt_embeddings"),
                 embeddings_file: str = "interrupt_embeddings",
                 openai_api_key: Optional[str] = None):
        self.phrases = INTERRUPT_PHRASES
        self.strict_phrases = ["wait", "hold on", "hold up", "one second", "one moment", "just a second"]
        super().__init__(embeddings_cache_path, embeddings_file, openai_api_key)

    async def is_interrupt(self, text: str) -> bool:
        return await self.is_similar(text)
