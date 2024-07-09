from typing import Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from vocode.streaming.output_device.rate_limit_interruptions_output_device import (
    RateLimitInterruptionsOutputDevice,
)
from vocode.streaming.telephony.constants import (
    PCM_SILENCE_BYTE,
    VONAGE_AUDIO_ENCODING,
    VONAGE_CHUNK_SIZE,
    VONAGE_SAMPLING_RATE,
)


class VonageOutputDevice(RateLimitInterruptionsOutputDevice):
    def __init__(
        self,
        ws: Optional[WebSocket] = None,
    ):
        super().__init__(sampling_rate=VONAGE_SAMPLING_RATE, audio_encoding=VONAGE_AUDIO_ENCODING)
        self.ws = ws

    async def play(self, chunk: bytes):
        for i in range(0, len(chunk), VONAGE_CHUNK_SIZE):
            subchunk = chunk[i : i + VONAGE_CHUNK_SIZE]
            if len(subchunk) % 2 == 1:
                subchunk += PCM_SILENCE_BYTE  # pad with silence, Vonage goes crazy otherwise
            if self.ws and self.ws.application_state != WebSocketState.DISCONNECTED:
                await self.ws.send_bytes(subchunk)
