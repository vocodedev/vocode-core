from __future__ import annotations

import asyncio
import base64
import json
from typing import Optional

from fastapi import WebSocket

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.telephony.constants import DEFAULT_AUDIO_ENCODING, DEFAULT_SAMPLING_RATE
from vocode.streaming.utils.create_task import asyncio_create_task_with_done_error_log


class TwilioOutputDevice(BaseOutputDevice):
    def __init__(self, ws: Optional[WebSocket] = None, stream_sid: Optional[str] = None):
        super().__init__(sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=DEFAULT_AUDIO_ENCODING)
        self.ws = ws
        self.stream_sid = stream_sid
        self.active = True
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.process_task = asyncio_create_task_with_done_error_log(self.process())

    async def process(self):
        while self.active:
            message = await self.queue.get()
            await self.ws.send_text(message)

    def consume_nonblocking(self, chunk: bytes):
        twilio_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
        }
        self.queue.put_nowait(json.dumps(twilio_message))

    def send_chunk_finished_mark(self, utterance_id, chunk_idx):
        mark_message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": f"chunk-{utterance_id}-{chunk_idx}",
            },
        }
        self.queue.put_nowait(json.dumps(mark_message))

    def send_utterance_finished_mark(self, utterance_id):
        mark_message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": f"utterance-{utterance_id}",
            },
        }
        self.queue.put_nowait(json.dumps(mark_message))

    def send_clear_message(self):
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid,
        }
        self.queue.put_nowait(json.dumps(clear_message))

    def terminate(self):
        self.process_task.cancel()
