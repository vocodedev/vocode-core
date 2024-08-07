from __future__ import annotations

from typing import Optional
from fastapi import WebSocket

from vocode.streaming.output_device.twilio_output_device import TwilioOutputDevice
from vocode.streaming.telephony.constants import EXOTEL_AUDIO_ENCODING


class ExotelOutputDevice(TwilioOutputDevice):
    def __init__(self, ws: Optional[WebSocket] = None, stream_sid: Optional[str] = None):
        super().__init__(ws, stream_sid, stream_sid_key="stream_sid", audio_encoding=EXOTEL_AUDIO_ENCODING)
