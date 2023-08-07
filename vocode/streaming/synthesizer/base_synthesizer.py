import os
from typing import (
    Any,
    AsyncGenerator,
    Generator,
    Callable,
    Generic,
    List,
    Optional,
    TypeVar,
)
import math
import io
import wave
import aiohttp
from nltk.tokenize import word_tokenize
from nltk.tokenize.treebank import TreebankWordDetokenizer
from opentelemetry import trace

from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.agent import FillerAudioConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils import convert_wav, get_chunk_size_per_second
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.synthesizer import SynthesizerConfig

FILLER_PHRASES = [
    BaseMessage(text="Um..."),
    BaseMessage(text="Uh..."),
    BaseMessage(text="Uh-huh..."),
    BaseMessage(text="Mm-hmm..."),
    BaseMessage(text="Hmm..."),
    BaseMessage(text="Okay..."),
    BaseMessage(text="Right..."),
    BaseMessage(text="Let me see..."),
]
FILLER_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "filler_audio")
TYPING_NOISE_PATH = "%s/typing-noise.wav" % FILLER_AUDIO_PATH


def encode_as_wav(chunk: bytes, synthesizer_config: SynthesizerConfig) -> bytes:
    output_bytes_io = io.BytesIO()
    in_memory_wav = wave.open(output_bytes_io, "wb")
    in_memory_wav.setnchannels(1)
    assert synthesizer_config.audio_encoding == AudioEncoding.LINEAR16
    in_memory_wav.setsampwidth(2)
    in_memory_wav.setframerate(synthesizer_config.sampling_rate)
    in_memory_wav.writeframes(chunk)
    output_bytes_io.seek(0)
    return output_bytes_io.read()


tracer = trace.get_tracer(__name__)


class SynthesisResult:
    class ChunkResult:
        def __init__(self, chunk: bytes, is_last_chunk: bool):
            self.chunk = chunk
            self.is_last_chunk = is_last_chunk

    def __init__(
        self,
        chunk_generator: AsyncGenerator[ChunkResult, None],
        get_message_up_to: Callable[[int], str],
    ):
        self.chunk_generator = chunk_generator
        self.get_message_up_to = get_message_up_to


class FillerAudio:
    def __init__(
        self,
        message: BaseMessage,
        audio_data: bytes,
        synthesizer_config: SynthesizerConfig,
        is_interruptible: bool = False,
        seconds_per_chunk: int = 1,
    ):
        self.message = message
        self.audio_data = audio_data
        self.synthesizer_config = synthesizer_config
        self.is_interruptible = is_interruptible
        self.seconds_per_chunk = seconds_per_chunk

    def create_synthesis_result(self) -> SynthesisResult:
        chunk_size = (
            get_chunk_size_per_second(
                self.synthesizer_config.audio_encoding,
                self.synthesizer_config.sampling_rate,
            )
            * self.seconds_per_chunk
        )

        async def chunk_generator(chunk_transform=lambda x: x):
            for i in range(0, len(self.audio_data), chunk_size):
                if i + chunk_size > len(self.audio_data):
                    yield SynthesisResult.ChunkResult(
                        chunk_transform(self.audio_data[i:]), True
                    )
                else:
                    yield SynthesisResult.ChunkResult(
                        chunk_transform(self.audio_data[i : i + chunk_size]), False
                    )

        if self.synthesizer_config.should_encode_as_wav:
            output_generator = chunk_generator(
                lambda chunk: encode_as_wav(chunk, self.synthesizer_config)
            )
        else:
            output_generator = chunk_generator()
        return SynthesisResult(output_generator, lambda seconds: self.message.text)


SynthesizerConfigType = TypeVar("SynthesizerConfigType", bound=SynthesizerConfig)


class BaseSynthesizer(Generic[SynthesizerConfigType]):
    def __init__(
        self,
        synthesizer_config: SynthesizerConfigType,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        self.synthesizer_config = synthesizer_config
        if synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            assert (
                synthesizer_config.sampling_rate == 8000
            ), "MuLaw encoding only supports 8kHz sampling rate"
        self.filler_audios: List[FillerAudio] = []
        if aiohttp_session:
            # the caller is responsible for closing the session
            self.aiohttp_session = aiohttp_session
            self.should_close_session_on_tear_down = False
        else:
            self.aiohttp_session = aiohttp.ClientSession()
            self.should_close_session_on_tear_down = True

    async def empty_generator(self):
        yield SynthesisResult.ChunkResult(b"", True)

    def get_synthesizer_config(self) -> SynthesizerConfig:
        return self.synthesizer_config

    def get_typing_noise_filler_audio(self) -> FillerAudio:
        return FillerAudio(
            message=BaseMessage(text="<typing noise>"),
            audio_data=convert_wav(
                TYPING_NOISE_PATH,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=self.synthesizer_config.audio_encoding,
            ),
            synthesizer_config=self.synthesizer_config,
            is_interruptible=True,
            seconds_per_chunk=2,
        )

    async def set_filler_audios(self, filler_audio_config: FillerAudioConfig):
        if filler_audio_config.use_phrases:
            self.filler_audios = await self.get_phrase_filler_audios()
        elif filler_audio_config.use_typing_noise:
            self.filler_audios = [self.get_typing_noise_filler_audio()]

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        return []

    def ready_synthesizer(self):
        pass

    # given the number of seconds the message was allowed to go until, where did we get in the message?
    def get_message_cutoff_from_total_response_length(
        self, message: BaseMessage, seconds: int, size_of_output: int
    ) -> str:
        estimated_output_seconds = (
            size_of_output / self.synthesizer_config.sampling_rate
        )
        if not message.text:
            return message.text

        estimated_output_seconds_per_char = estimated_output_seconds / len(message.text)
        return message.text[: int(seconds / estimated_output_seconds_per_char)]

    def get_message_cutoff_from_voice_speed(
        self, message: BaseMessage, seconds: int, words_per_minute: int
    ) -> str:
        words_per_second = words_per_minute / 60
        estimated_words_spoken = math.floor(words_per_second * seconds)
        tokens = word_tokenize(message.text)
        return TreebankWordDetokenizer().detokenize(tokens[:estimated_words_spoken])

    # returns a chunk generator and a thunk that can tell you what part of the message was read given the number of seconds spoken
    # chunk generator must return a ChunkResult, essentially a tuple (bytes of size chunk_size, flag if it is the last chunk)
    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        raise NotImplementedError

    # @param file - a file-like object in wav format
    def create_synthesis_result_from_wav(
        self, file: Any, message: BaseMessage, chunk_size: int
    ) -> SynthesisResult:
        output_bytes = convert_wav(
            file,
            output_sample_rate=self.synthesizer_config.sampling_rate,
            output_encoding=self.synthesizer_config.audio_encoding,
        )

        if self.synthesizer_config.should_encode_as_wav:
            chunk_transform = lambda chunk: encode_as_wav(
                chunk, self.synthesizer_config
            )
        else:
            chunk_transform = lambda chunk: chunk

        async def chunk_generator(output_bytes):
            for i in range(0, len(output_bytes), chunk_size):
                if i + chunk_size > len(output_bytes):
                    yield SynthesisResult.ChunkResult(
                        chunk_transform(output_bytes[i:]), True
                    )
                else:
                    yield SynthesisResult.ChunkResult(
                        chunk_transform(output_bytes[i : i + chunk_size]), False
                    )

        return SynthesisResult(
            chunk_generator(output_bytes),
            lambda seconds: self.get_message_cutoff_from_total_response_length(
                message, seconds, len(output_bytes)
            ),
        )

    async def tear_down(self):
        if self.should_close_session_on_tear_down:
            await self.aiohttp_session.close()
