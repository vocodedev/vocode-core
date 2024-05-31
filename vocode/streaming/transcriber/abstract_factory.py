from abc import ABC, abstractmethod

from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.transcriber.base_transcriber import (
    BaseAsyncTranscriber,
    BaseThreadAsyncTranscriber,
)


class AbstractTranscriberFactory(ABC):
    @abstractmethod
    def create_transcriber(
        self,
        transcriber_config: TranscriberConfig,
    ) -> BaseAsyncTranscriber[TranscriberConfig] | BaseThreadAsyncTranscriber[TranscriberConfig]:
        pass
