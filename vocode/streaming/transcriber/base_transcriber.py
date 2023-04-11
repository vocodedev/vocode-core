from typing import Callable, Optional, Awaitable

from vocode.streaming.utils import convert_wav
from vocode.streaming.models.transcriber import EndpointingConfig, TranscriberConfig


class Transcription:
    def __init__(
        self,
        message: str,
        confidence: float,
        is_final: bool,
        is_interrupt: bool = False,
    ):
        self.message = message
        self.confidence = confidence
        self.is_final = is_final
        self.is_interrupt = is_interrupt

    def __str__(self):
        return f"Transcription({self.message}, {self.confidence}, {self.is_final})"


class BaseTranscriber:
    def __init__(
        self,
        transcriber_config: TranscriberConfig,
    ):
        self.transcriber_config = transcriber_config
        self.on_response: Optional[Callable[[Transcription], Awaitable]] = None

    def get_transcriber_config(self) -> TranscriberConfig:
        return self.transcriber_config

    def set_on_response(self, on_response: Callable[[Transcription], Awaitable]):
        self.on_response = on_response

    async def ready(self):
        return True

    async def run(self):
        pass

    def send_audio(self, chunk):
        pass

    def terminate(self):
        pass
