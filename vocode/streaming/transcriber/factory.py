import logging
from typing import Optional
from vocode.streaming.models.transcriber import TranscriberConfig, TranscriberType
from vocode.streaming.transcriber.assembly_ai_transcriber import AssemblyAITranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.google_transcriber import GoogleTranscriber


class TranscriberFactory:
    def create_transcriber(
        self,
        transcriber_config: TranscriberConfig,
        logger: Optional[logging.Logger] = None,
    ):
        if transcriber_config.type == TranscriberType.DEEPGRAM:
            return DeepgramTranscriber(transcriber_config, logger=logger)
        elif transcriber_config.type == TranscriberType.GOOGLE:
            return GoogleTranscriber(transcriber_config, logger=logger)
        elif transcriber_config.type == TranscriberType.ASSEMBLY_AI:
            return AssemblyAITranscriber(transcriber_config, logger=logger)
        else:
            raise Exception("Invalid transcriber config")
