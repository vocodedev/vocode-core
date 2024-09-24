from __future__ import annotations
from typing import Optional

import asyncio
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
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

    def start(self):
        self.active = True
        self.process_task = asyncio.create_task(self.process())

    def mark_closed(self):
        self.active = False

    async def process(self):
        while self.active:
            message = await self.queue.get()
            if self.active and self.ws.client_state != WebSocketState.DISCONNECTED:
                await self.ws.send_text(message)

    def consume_nonblocking(self, chunk: bytes, lipsync_events: Optional[list] = None):
        if self.active:
            audio_message = AudioMessage.from_bytes(chunk)
            if lipsync_events:
                audio_message.lipsync_events = lipsync_events
            self.queue.put_nowait(audio_message.json())

    def consume_transcript(self, event: TranscriptEvent):
        if self.active:
            transcript_message = TranscriptMessage.from_event(event)
            self.queue.put_nowait(transcript_message.json())

    def terminate(self):
        self.process_task.cancel()
