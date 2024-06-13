import asyncio
from typing import Dict, Union

from pydantic.v1 import BaseModel


class ChunkFinishedMarkMessage(BaseModel):
    chunk_idx: int


class UtteranceFinishedMarkMessage(BaseModel):
    pass


MarkMessage = Union[ChunkFinishedMarkMessage, UtteranceFinishedMarkMessage]


class MarkMessageQueue:
    """A keyed asyncio.Queue for MarkMessage objects"""

    def __init__(self):
        self.utterance_queues: Dict[str, asyncio.Queue[MarkMessage]] = {}

    def create_utterance_queue(self, utterance_id: str):
        if utterance_id in self.utterance_queues:
            raise ValueError(f"utterance_id {utterance_id} already exists")
        self.utterance_queues[utterance_id] = asyncio.Queue()

    def put_nowait(
        self,
        utterance_id: str,
        mark_message: MarkMessage,
    ):
        if utterance_id in self.utterance_queues:
            self.utterance_queues[utterance_id].put_nowait(mark_message)

    async def get(
        self,
        utterance_id: str,
    ) -> MarkMessage:
        if utterance_id not in self.utterance_queues:
            raise ValueError(f"utterance_id {utterance_id} not found")
        return await self.utterance_queues[utterance_id].get()

    def delete_utterance_queue(self, utterance_id: str):
        del self.utterance_queues[utterance_id]
