import asyncio
from dataclasses import dataclass
from enum import Enum


class ChunkState(int, Enum):
    UNPLAYED = 0
    PLAYED = 1
    INTERRUPTED = 2


@dataclass
class AudioChunk:
    data: bytes
    state: ChunkState = ChunkState.UNPLAYED

    @staticmethod
    def on_play():
        pass

    @staticmethod
    def on_interrupt():
        pass
