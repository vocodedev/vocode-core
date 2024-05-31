from abc import ABC, abstractmethod

from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.utils.async_requester import AsyncRequestor


class AbstractSynthesizerFactory(ABC):
    # TODO(DOW-48): Make this not require async_requestor
    @abstractmethod
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
    ) -> BaseSynthesizer:
        pass
