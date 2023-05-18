import logging
from typing import Optional
import typing
from vocode.streaming.models.transcriber import (
    AssemblyAITranscriberConfig,
    AzureTranscriberConfig,
    DeepgramTranscriberConfig,
    GoogleTranscriberConfig,
    RevAITranscriberConfig,
    TranscriberConfig,
    TranscriberType,
)
from vocode.streaming.transcriber.assembly_ai_transcriber import AssemblyAITranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.google_transcriber import GoogleTranscriber
from vocode.streaming.transcriber.rev_ai_transcriber import RevAITranscriber
from vocode.streaming.transcriber.azure_transcriber import AzureTranscriber


class TranscriberFactory:
    def create_transcriber(
        self,
        transcriber_config: TranscriberConfig,
        logger: Optional[logging.Logger] = None,
    ):
        if transcriber_config.type == TranscriberType.DEEPGRAM:
            return DeepgramTranscriber(
                typing.cast(DeepgramTranscriberConfig, transcriber_config),
                logger=logger,
            )
        elif transcriber_config.type == TranscriberType.GOOGLE:
            return GoogleTranscriber(
                typing.cast(GoogleTranscriberConfig, transcriber_config), logger=logger
            )
        elif transcriber_config.type == TranscriberType.ASSEMBLY_AI:
            return AssemblyAITranscriber(
                typing.cast(AssemblyAITranscriberConfig, transcriber_config),
                logger=logger,
            )
        elif transcriber_config.type == TranscriberType.REV_AI:
            return RevAITranscriber(
                typing.cast(RevAITranscriberConfig, transcriber_config), logger=logger
            )
        elif transcriber_config.type == TranscriberType.AZURE:
            return AzureTranscriber(
                typing.cast(AzureTranscriberConfig, transcriber_config), logger=logger
            )
        else:
            raise Exception("Invalid transcriber config")
