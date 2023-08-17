import logging
from typing import Optional
import typing
import aiohttp

from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    CoquiTTSSynthesizerConfig,
    ElevenLabsSynthesizerConfig,
    GTTSSynthesizerConfig,
    GoogleSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
    PollySynthesizerConfig,
    StreamElementsSynthesizerConfig,
    SynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.google_synthesizer import GoogleSynthesizer
from vocode.streaming.synthesizer.gtts_synthesizer import GTTSSynthesizer
from vocode.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode.streaming.synthesizer.rime_synthesizer import RimeSynthesizer
from vocode.streaming.synthesizer.polly_synthesizer import PollySynthesizer
from vocode.streaming.synthesizer.stream_elements_synthesizer import (
    StreamElementsSynthesizer,
)
from vocode.streaming.synthesizer.coqui_tts_synthesizer import CoquiTTSSynthesizer


class SynthesizerFactory:
    def create_synthesizer(
        self,
        synthesizer_config: SynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        if isinstance(synthesizer_config, GoogleSynthesizerConfig):
            return GoogleSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, AzureSynthesizerConfig):
            return AzureSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, ElevenLabsSynthesizerConfig):
            return ElevenLabsSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, PlayHtSynthesizerConfig):
            return PlayHtSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, RimeSynthesizerConfig):
            return RimeSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, GTTSSynthesizerConfig):
            return GTTSSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, StreamElementsSynthesizerConfig):
            return StreamElementsSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, CoquiTTSSynthesizerConfig):
            return CoquiTTSSynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        elif isinstance(synthesizer_config, PollySynthesizerConfig):
            return PollySynthesizer(
                synthesizer_config, logger=logger, aiohttp_session=aiohttp_session
            )
        else:
            raise Exception("Invalid synthesizer config")
