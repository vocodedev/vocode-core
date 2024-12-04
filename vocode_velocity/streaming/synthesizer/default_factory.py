from typing import Type

from vocode_velocity.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    CartesiaSynthesizerConfig,
    ElevenLabsSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
    StreamElementsSynthesizerConfig,
    SynthesizerConfig,
)
from vocode_velocity.streaming.synthesizer.abstract_factory import AbstractSynthesizerFactory
from vocode_velocity.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode_velocity.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode_velocity.streaming.synthesizer.cartesia_synthesizer import CartesiaSynthesizer
from vocode_velocity.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode_velocity.streaming.synthesizer.eleven_labs_websocket_synthesizer import ElevenLabsWSSynthesizer
from vocode_velocity.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode_velocity.streaming.synthesizer.play_ht_synthesizer_v2 import PlayHtSynthesizerV2
from vocode_velocity.streaming.synthesizer.rime_synthesizer import RimeSynthesizer
from vocode_velocity.streaming.synthesizer.stream_elements_synthesizer import StreamElementsSynthesizer


class DefaultSynthesizerFactory(AbstractSynthesizerFactory):
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
    ):
        if isinstance(synthesizer_config, AzureSynthesizerConfig):
            return AzureSynthesizer(synthesizer_config)
        elif isinstance(synthesizer_config, CartesiaSynthesizerConfig):
            return CartesiaSynthesizer(synthesizer_config)
        elif isinstance(synthesizer_config, ElevenLabsSynthesizerConfig):
            eleven_labs_synthesizer_class_type: Type[BaseSynthesizer] = ElevenLabsSynthesizer
            if synthesizer_config.experimental_websocket:
                eleven_labs_synthesizer_class_type = ElevenLabsWSSynthesizer
            return eleven_labs_synthesizer_class_type(synthesizer_config)
        elif isinstance(synthesizer_config, PlayHtSynthesizerConfig):
            if synthesizer_config.version == "2":
                return PlayHtSynthesizerV2(synthesizer_config)
            else:
                return PlayHtSynthesizer(synthesizer_config)
        elif isinstance(synthesizer_config, RimeSynthesizerConfig):
            return RimeSynthesizer(synthesizer_config)
        elif isinstance(synthesizer_config, StreamElementsSynthesizerConfig):
            return StreamElementsSynthesizer(synthesizer_config)
        else:
            raise Exception("Invalid synthesizer config")
