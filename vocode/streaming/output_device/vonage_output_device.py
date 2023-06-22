import asyncio
from typing import Optional
import wave

from fastapi import WebSocket
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.output_device.speaker_output import SpeakerOutput
from vocode.streaming.telephony.constants import (
    VONAGE_AUDIO_ENCODING,
    VONAGE_CHUNK_SIZE,
    VONAGE_SAMPLING_RATE,
)


class VonageOutputDevice(BaseOutputDevice):
    def __init__(
        self,
        ws: Optional[WebSocket] = None,
        output_to_speaker: bool = False,
    ):
        super().__init__(
            sampling_rate=VONAGE_SAMPLING_RATE, audio_encoding=VONAGE_AUDIO_ENCODING
        )
        self.ws = ws
        self.active = True
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.process_task = asyncio.create_task(self.process())
        self.output_to_speaker = output_to_speaker
        if output_to_speaker:
            self.output_speaker = SpeakerOutput.from_default_device(
                sampling_rate=VONAGE_SAMPLING_RATE, blocksize=VONAGE_CHUNK_SIZE // 2
            )

    async def process(self):
        while self.active:
            chunk = await self.queue.get()
            if self.output_to_speaker:
                self.output_speaker.consume_nonblocking(chunk)
            for i in range(0, len(chunk), VONAGE_CHUNK_SIZE):
                subchunk = chunk[i : i + VONAGE_CHUNK_SIZE]
                await self.ws.send_bytes(subchunk)

    def consume_nonblocking(self, chunk: bytes):
        self.queue.put_nowait(chunk)

    def maybe_send_mark_nonblocking(self, message_sent):
        pass

    def terminate(self):
        self.process_task.cancel()
