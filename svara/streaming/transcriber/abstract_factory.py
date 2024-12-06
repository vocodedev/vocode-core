from abc import ABC, abstractmethod

from svara.streaming.models.transcriber import TranscriberConfig
from svara.streaming.transcriber.base_transcriber import (
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
