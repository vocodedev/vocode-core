from __future__ import annotations

import asyncio
from fastapi import WebSocket
import numpy as np
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.models.websocket import AudioMessage
from vocode.streaming.models.websocket import TranscriptMessage
from vocode.streaming.models.transcript import TranscriptEvent


def convert_linear16_to_pcm(linear16_audio: bytes) -> bytes:
    audio_array = (
        np.frombuffer(linear16_audio, dtype=np.int16).astype(np.float32) / 32768.0
    )
    return audio_array.tobytes()


class WebsocketOutputDevice(BaseOutputDevice):
    def __init__(
        self,
        ws: WebSocket,
        sampling_rate: int,
        audio_encoding: AudioEncoding,
        into_pcm: bool = False,
    ):
        super().__init__(sampling_rate, audio_encoding)
        self.ws = ws
        self.active = False
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.into_pcm = into_pcm

    def start(self):
        self.active = True
        self.process_task = asyncio.create_task(self.process())

    def mark_closed(self):
        self.active = False

    async def process(self):
        while self.active:
            message = await self.queue.get()
            await self.ws.send_text(message)

    def consume_nonblocking(self, chunk: bytes):
        if self.active:
            if self.into_pcm:
                # I need to test this in my next pr, since I need to fix up the ws to use StateAgent first
                if self.audio_encoding == AudioEncoding.LINEAR16:
                    chunk = convert_linear16_to_pcm(chunk)
                elif self.audio_encoding == AudioEncoding.MULAW:
                    raise ValueError("Mu-law encoding is not supported yet")
                else:
                    raise ValueError(
                        f"Unsupported audio encoding: {self.audio_encoding}"
                    )
            audio_message = AudioMessage.from_bytes(chunk)

            self.queue.put_nowait(audio_message.json())

    def consume_transcript(self, event: TranscriptEvent):
        if self.active:
            transcript_message = TranscriptMessage.from_event(event)
            self.queue.put_nowait(transcript_message.json())

    def terminate(self):
        self.process_task.cancel()

    def clear(self):
        while not self.queue.empty():
            self.queue.get_nowait()
