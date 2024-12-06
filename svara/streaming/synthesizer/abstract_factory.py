from abc import ABC, abstractmethod

from svara.streaming.models.synthesizer import SynthesizerConfig
from svara.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from svara.streaming.utils.async_requester import AsyncRequestor


class AbstractSynthesizerFactory(ABC):
    # TODO(DOW-48): Make this not require async_requestor
    @abstractmethod
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
    ) -> BaseSynthesizer:
        pass
