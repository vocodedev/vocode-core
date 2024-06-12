from __future__ import annotations

import asyncio
import base64
import json
from typing import Optional
import uuid

from fastapi import WebSocket

from vocode.streaming.output_device.audio_chunk import AudioChunk, ChunkState
from vocode.streaming.output_device.abstract_output_device import AbstractOutputDevice
from vocode.streaming.telephony.constants import DEFAULT_AUDIO_ENCODING, DEFAULT_SAMPLING_RATE
from vocode.streaming.telephony.conversation.mark_message_queue import MarkMessage
from vocode.streaming.utils.create_task import asyncio_create_task_with_done_error_log
from vocode.streaming.utils.worker import InterruptibleEvent


class TwilioOutputDevice(AbstractOutputDevice):
    def __init__(self, ws: Optional[WebSocket] = None, stream_sid: Optional[str] = None):
        super().__init__(sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=DEFAULT_AUDIO_ENCODING)
        self.ws = ws
        self.stream_sid = stream_sid
        self.active = True

        self.twilio_events_queue: asyncio.Queue[str] = asyncio.Queue()
        self.mark_message_queue: asyncio.Queue[MarkMessage] = asyncio.Queue()
        self.unprocessed_audio_chunks_queue: asyncio.Queue[InterruptibleEvent[AudioChunk]] = (
            asyncio.Queue()
        )

    def enqueue_mark_message(self, mark_message: MarkMessage):
        self.mark_message_queue.put_nowait(mark_message)

    async def _send_twilio_messages(self):
        while True:
            try:
                twilio_event = await self.twilio_events_queue.get()
            except asyncio.CancelledError:
                return

            await self.ws.send_text(twilio_event)

    async def _process_mark_messages(self):
        while True:
            try:
                mark_message = await self.mark_message_queue.get()
                item = await self.unprocessed_audio_chunks_queue.get()
                # TODO: cross reference chunk IDs?
            except asyncio.CancelledError:
                return

            self.interruptible_event = item
            audio_chunk = item.payload

            if item.is_interrupted():
                audio_chunk.on_interrupt()
                audio_chunk.state = ChunkState.INTERRUPTED
                continue

            await self.play(audio_chunk.data)
            audio_chunk.on_play()
            audio_chunk.state = ChunkState.PLAYED

            self.interruptible_event.is_interruptible = False

    async def _run_loop(self):
        send_twilio_messages_task = asyncio_create_task_with_done_error_log(
            self._send_twilio_messages()
        )
        process_mark_messages_task = asyncio_create_task_with_done_error_log(
            self._process_mark_messages()
        )
        await asyncio.gather(send_twilio_messages_task, process_mark_messages_task)

    def consume_nonblocking(self, item: InterruptibleEvent[AudioChunk]):
        # TODO: think about when interrupted messages enter the queue + synchronicity with the clear message
        if not item.is_interrupted():
            self.send_audio_chunk_and_mark(item.payload.data)
            self.unprocessed_audio_chunks_queue.put_nowait(item)

    async def play(self, chunk: bytes):
        # TODO comment
        pass

    def interrupt(self):
        self.send_clear_message()

    def send_audio_chunk_and_mark(self, chunk: bytes):
        media_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
        }
        self.twilio_events_queue.put_nowait(json.dumps(media_message))
        mark_message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": str(uuid.uuid4()),
            },
        }
        self.twilio_events_queue.put_nowait(json.dumps(mark_message))

    def send_clear_message(self):
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid,
        }
        self.twilio_events_queue.put_nowait(json.dumps(clear_message))
