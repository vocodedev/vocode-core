from __future__ import annotations

from pydub import AudioSegment
import asyncio
import io
import base64
from fastapi import WebSocket
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.models.websocket import AudioMessage
from vocode.streaming.models.websocket import TranscriptMessage
from vocode.streaming.models.transcript import TranscriptEvent



class WebsocketOutputDevice(BaseOutputDevice):
    def __init__(
        self, ws: WebSocket, sampling_rate: int, audio_encoding: AudioEncoding
    ):
        super().__init__(sampling_rate, audio_encoding)
        self.ws = ws
        self.active = False
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    def convert_to_mp3(self, chunk: bytes) -> bytes:
            # Assuming chunk is raw audio data
            audio = AudioSegment.from_raw(io.BytesIO(chunk), 
                                        sample_width=2, # 2 bytes for 16-bit audio
                                        frame_rate=self.sampling_rate, 
                                        channels=1) # mono
            buffer = io.BytesIO()
            audio.export(buffer, format="mp3")
            return buffer.getvalue()

    def consume_nonblocking(self, chunk: bytes):
        if self.active:
            mp3_data = self.convert_to_mp3(chunk)
            base64_encoded_mp3 = base64.b64encode(mp3_data).decode('utf-8')
            audio_message = AudioMessage(data=base64_encoded_mp3)
            self.queue.put_nowait(audio_message.json())

    def start(self):
        self.active = True
        self.process_task = asyncio.create_task(self.process())

    def mark_closed(self):
        self.active = False

    async def process(self):
        while self.active:
            message = await self.queue.get()
            await self.ws.send(message)

    def consume_transcript(self, event: TranscriptEvent):
        if self.active:
            transcript_message = TranscriptMessage.from_event(event)
            self.queue.put_nowait(transcript_message.json())

    def terminate(self):
        self.process_task.cancel()
