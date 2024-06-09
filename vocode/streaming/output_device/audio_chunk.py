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
    state: ChunkState

    def on_play(self):
        self.state = ChunkState.PLAYED

    def on_interrupt(self):
        self.state = ChunkState.INTERRUPTED


@dataclass
class UtteranceAudioChunk(AudioChunk):
    chunk_idx: int
    processed_event: asyncio.Event
