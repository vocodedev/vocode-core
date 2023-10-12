import datetime
import logging
import os
from typing import Optional

from vocode.streaming.utils.embedding_model import EmbeddingModel

SIMILARITY_THRESHOLD = 0.9
EMBEDDING_SIZE = 1536
INTERRUPT_PHRASES = [
    "just a moment",
    "just a minute",
    "just a sec",
    "Excuse me",
    # "I'm sorry to interrupt",
    # "Sorry, but I think",
    # "Just a quick point",
    # "Hang on a sec, I have something to say",
    # "Wait, let me stop you there",
    # "Before you continue, I wanted to mention",
    # "I hate to cut you off, but",
    # "I'd like to chime in",
    # "Can I offer my perspective",
    # "I'd like to share my thoughts on this",
    # "Let me quickly mention",
    # "Can I jump in here for a moment",
    # "Pardon me, but I'd like to say",
]


class InterruptModel(EmbeddingModel):
    def __init__(self, embeddings_cache_path=os.path.join(os.path.dirname(__file__), "interrupt_embeddings"),
                 embeddings_file: str = "interrupt_embeddings",
                 openai_api_key: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.strict_phrases = ["wait", "hold on", "hold up", "one second", "one moment", "just a second", "hang on"]
        self.phrases = self.strict_phrases + INTERRUPT_PHRASES
        super().__init__(embeddings_cache_path, embeddings_file, openai_api_key, logger)

    async def is_interrupt(self, text: str) -> bool:
        self.logger.debug(f"checking if interrupt: {text}")
        time = datetime.datetime.now()
        is_similar = await self.is_similar(text)
        self.logger.debug(f"is_interrupt:{is_similar}, took: {datetime.datetime.now() - time}")
        return is_similar
