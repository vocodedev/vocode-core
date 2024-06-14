import asyncio
from typing import Optional

from fastapi import WebSocket

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.output_device.blocking_speaker_output import BlockingSpeakerOutput
from vocode.streaming.telephony.constants import (
    PCM_SILENCE_BYTE,
    VONAGE_AUDIO_ENCODING,
    VONAGE_CHUNK_SIZE,
    VONAGE_SAMPLING_RATE,
)
from vocode.streaming.utils.create_task import asyncio_create_task_with_done_error_log


class VonageOutputDevice(BaseOutputDevice):
    def __init__(
        self,
        ws: Optional[WebSocket] = None,
        output_to_speaker: bool = False,
    ):
        super().__init__(sampling_rate=VONAGE_SAMPLING_RATE, audio_encoding=VONAGE_AUDIO_ENCODING)
        self.ws = ws
        self.active = True
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.process_task = asyncio_create_task_with_done_error_log(self.process())
        self.output_to_speaker = output_to_speaker
        if output_to_speaker:
            self.output_speaker = BlockingSpeakerOutput.from_default_device(
                sampling_rate=VONAGE_SAMPLING_RATE, blocksize=VONAGE_CHUNK_SIZE // 2
            )

    async def process(self):
        while self.active:
            chunk = await self.queue.get()
            if self.output_to_speaker:
                self.output_speaker.consume_nonblocking(chunk)
            for i in range(0, len(chunk), VONAGE_CHUNK_SIZE):
                subchunk = chunk[i : i + VONAGE_CHUNK_SIZE]
                if len(subchunk) % 2 == 1:
                    subchunk += PCM_SILENCE_BYTE  # pad with silence, Vonage goes crazy otherwise
                await self.ws.send_bytes(subchunk)

    def consume_nonblocking(self, chunk: bytes):
        self.queue.put_nowait(chunk)

    def terminate(self):
        self.process_task.cancel()
