from vocode.streaming.models.transcriber import (
    AssemblyAITranscriberConfig,
    AzureTranscriberConfig,
    DeepgramTranscriberConfig,
    GladiaTranscriberConfig,
    GoogleTranscriberConfig,
    RevAITranscriberConfig,
    TranscriberConfig,
)
from vocode.streaming.transcriber.abstract_factory import AbstractTranscriberFactory
from vocode.streaming.transcriber.assembly_ai_transcriber import AssemblyAITranscriber
from vocode.streaming.transcriber.azure_transcriber import AzureTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.gladia_transcriber import GladiaTranscriber
from vocode.streaming.transcriber.google_transcriber import GoogleTranscriber
from vocode.streaming.transcriber.rev_ai_transcriber import RevAITranscriber


class DefaultTranscriberFactory(AbstractTranscriberFactory):
    def create_transcriber(
        self,
        transcriber_config: TranscriberConfig,
    ):
        if isinstance(transcriber_config, DeepgramTranscriberConfig):
            return DeepgramTranscriber(transcriber_config)
        elif isinstance(transcriber_config, GoogleTranscriberConfig):
            return GoogleTranscriber(transcriber_config)
        elif isinstance(transcriber_config, AssemblyAITranscriberConfig):
            return AssemblyAITranscriber(transcriber_config)
        elif isinstance(transcriber_config, RevAITranscriberConfig):
            return RevAITranscriber(transcriber_config)
        elif isinstance(transcriber_config, AzureTranscriberConfig):
            return AzureTranscriber(transcriber_config)
        elif isinstance(transcriber_config, GladiaTranscriberConfig):
            return GladiaTranscriber(transcriber_config)
        else:
            raise Exception("Invalid transcriber config")
