import logging
from typing import Optional

from vocode.streaming.models.synthesizer import SynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.google_synthesizer import GoogleSynthesizer
from vocode.streaming.synthesizer.gtts_synthesizer import GTTSSynthesizer
from vocode.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode.streaming.synthesizer.rime_synthesizer import RimeSynthesizer
from vocode.streaming.synthesizer.stream_elements_synthesizer import StreamElementsSynthesizer


class SynthesizerFactory:
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        if synthesizer_config.type == SynthesizerType.GOOGLE:
            return GoogleSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.AZURE:
            return AzureSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.ELEVEN_LABS:
            return ElevenLabsSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.PLAY_HT:
            return PlayHtSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.RIME:
            return RimeSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.GTTS:
            return GTTSSynthesizer(synthesizer_config, logger=logger)
        elif synthesizer_config.type == SynthesizerType.STREAM_ELEMENTS:
            return StreamElementsSynthesizer(synthesizer_config, logger=logger)
        else:
            raise Exception("Invalid synthesizer config")
