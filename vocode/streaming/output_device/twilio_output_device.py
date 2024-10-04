from __future__ import annotations

import asyncio
import json
import base64
import logging
from typing import Optional

from fastapi import WebSocket

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_SAMPLING_RATE,
)


class TwilioOutputDevice(BaseOutputDevice):
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        ws: Optional[WebSocket] = None,
        stream_sid: Optional[str] = None,
    ):
        super().__init__(
            sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=DEFAULT_AUDIO_ENCODING
        )
        self.logger = logger
        self.ws = ws
        self.stream_sid = stream_sid
        self.active = True
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.process_task = asyncio.create_task(self.process())

    async def process(self):
        while self.active:
            message = await self.queue.get()
            await self.ws.send_text(message)

    async def clear(self):
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid,
        }
        while not self.queue.empty():
            await self.queue.get()
        # self.logger.debug(f"Sending clear message: {clear_message}")
        await self.queue.put(json.dumps(clear_message))

    async def consume_nonblocking(self, chunk: bytes):

        twilio_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
        }
        await self.queue.put(json.dumps(twilio_message))

    def maybe_send_mark_nonblocking(self, message_sent):
        mark_message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": "Sent {}".format(message_sent),
            },
        }
        self.queue.put_nowait(json.dumps(mark_message))

    def terminate(self):
        self.process_task.cancel()
