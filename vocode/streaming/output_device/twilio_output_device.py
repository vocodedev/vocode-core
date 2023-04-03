import json
import base64

from fastapi import WebSocket

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_SAMPLING_RATE,
)


class TwilioOutputDevice(BaseOutputDevice):
    def __init__(self, ws: WebSocket = None, stream_sid: str = None):
        super().__init__(
            sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=DEFAULT_AUDIO_ENCODING
        )
        self.ws = ws
        self.stream_sid = stream_sid

    async def send_async(self, chunk: bytes):
        twilio_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
        }
        await self.ws.send_text(json.dumps(twilio_message))

    async def maybe_send_mark_async(self, message_sent):
        mark_message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": "Sent {}".format(message_sent),
            },
        }
        await self.ws.send_text(json.dumps(mark_message))
