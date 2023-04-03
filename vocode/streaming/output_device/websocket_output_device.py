from fastapi import WebSocket
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.models.websocket import AudioMessage


class WebsocketOutputDevice(BaseOutputDevice):
    def __init__(
        self, ws: WebSocket, sampling_rate: int, audio_encoding: AudioEncoding
    ):
        super().__init__(sampling_rate, audio_encoding)
        self.ws = ws
        self.active = True

    def mark_closed(self):
        self.active = False

    async def send_async(self, chunk: bytes):
        if self.active:
            audio_message = AudioMessage.from_bytes(chunk)
            await self.ws.send_text(audio_message.json())

    async def maybe_send_mark_async(self, message):
        pass
