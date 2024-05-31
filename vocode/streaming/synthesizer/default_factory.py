from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    ElevenLabsSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
    StreamElementsSynthesizerConfig,
    SynthesizerConfig,
)
from vocode.streaming.synthesizer.abstract_factory import AbstractSynthesizerFactory
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode.streaming.synthesizer.play_ht_synthesizer_v2 import PlayHtSynthesizerV2
from vocode.streaming.synthesizer.rime_synthesizer import RimeSynthesizer
from vocode.streaming.synthesizer.stream_elements_synthesizer import StreamElementsSynthesizer


class DefaultSynthesizerFactory(AbstractSynthesizerFactory):
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
    ):
        if isinstance(synthesizer_config, AzureSynthesizerConfig):
            return AzureSynthesizer(synthesizer_config)
        elif isinstance(synthesizer_config, ElevenLabsSynthesizerConfig):
            return ElevenLabsSynthesizer(synthesizer_config)
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
