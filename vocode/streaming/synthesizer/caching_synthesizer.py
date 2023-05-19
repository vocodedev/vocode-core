import hashlib
import os
import re
from typing import Any, AsyncGenerator, Callable, Optional, List, Union
import wave
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.agent import FillerAudioConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, FillerAudio, SynthesisResult, ChunkResult


def save_as_wav(path, audio_data: bytes, config: Union[SynthesizerConfig, TranscriberConfig]):
    with open(path, "wb") as f:
        wav_file = wave.open(f, "wb")
        wav_file.setnchannels(1)
        assert config.audio_encoding == AudioEncoding.LINEAR16
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sampling_rate)
        wav_file.writeframes(audio_data)
        wav_file.close()

def cache_key(text, synthesizer_config: SynthesizerConfig) -> str:
    config_text = synthesizer_config.json()
    cleaned_text = text.lower()
    cleaned_text = re.sub(r'\s+', '-', cleaned_text)
    cleaned_text = re.sub(r'[|<>"?*:\\.$[\]#/@]', '', cleaned_text)

    hash_value = hashlib.md5((cleaned_text + config_text).encode()).hexdigest()[:8]
    return f"synth_{cleaned_text[:32]}_{hash_value}.wav"

class AsyncGeneratorWrapper(AsyncGenerator[ChunkResult, None]):
    def __init__(self, generator, when_finished: Callable):
        self.generator = generator
        self.all_bytes = bytearray()
        self.when_finished = when_finished

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk_result = await self.generator.__anext__()
            self.all_bytes += chunk_result.chunk
            return chunk_result
        except StopAsyncIteration:
            # Code to run when the async generator has finished
            # if not cut_off:
            self.when_finished(self.all_bytes)
            self.all_bytes = None
            raise
    
    async def asend(self, value):
        return await self.generator.asend(value)

    async def athrow(self, type, value=None, traceback=None):
        return await self.generator.athrow(type, value, traceback)

class CachingSynthesizer(BaseSynthesizer):

    def __init__(self, inner_synthesizer: BaseSynthesizer, cache_path: str = "cache"):
        self.inner_synthesizer = inner_synthesizer
        self.cache_path = cache_path
        os.makedirs(self.cache_path, exist_ok=True)
    
    @property
    def filler_audios(self) -> List[FillerAudio]:
        return self.inner_synthesizer.filler_audios

    def get_synthesizer_config(self) -> SynthesizerConfig:
        return self.inner_synthesizer.get_synthesizer_config()

    def get_typing_noise_filler_audio(self) -> FillerAudio:
        return self.inner_synthesizer.get_typing_noise_filler_audio()

    async def set_filler_audios(self, filler_audio_config: FillerAudioConfig):
        await self.inner_synthesizer.set_filler_audios(filler_audio_config)

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        return await self.inner_synthesizer.get_phrase_filler_audios();

    def ready_synthesizer(self):
        return self.inner_synthesizer.ready_synthesizer()

    def get_message_cutoff_from_total_response_length(
        self, message: BaseMessage, seconds: int, size_of_output: int
    ) -> str:
        return self.inner_synthesizer.get_message_cutoff_from_total_response_length(message, seconds, size_of_output)

    def get_message_cutoff_from_voice_speed(
        self, message: BaseMessage, seconds: int, words_per_minute: int
    ) -> str:
        return self.inner_synthesizer.get_message_cutoff_from_voice_speed(message, seconds, words_per_minute)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        cached_path = os.path.join(self.cache_path, cache_key(message.text, self.inner_synthesizer.get_synthesizer_config()))
        if os.path.exists(cached_path):
            with open(cached_path, "rb") as f:
                result = self.inner_synthesizer.create_synthesis_result_from_wav(f, message, chunk_size)
        else:
            result = await self.inner_synthesizer.create_speech(message, chunk_size, bot_sentiment)
        
        def save_synthesis(all_bytes):
            save_as_wav(cached_path, all_bytes, self.inner_synthesizer.get_synthesizer_config())

        result.chunk_generator = AsyncGeneratorWrapper(result.chunk_generator, save_synthesis)
        result.cached_path = cached_path
        return result

    # @param file - a file-like object in wav format
    def create_synthesis_result_from_wav(
        self, file: Any, message: BaseMessage, chunk_size: int
    ) -> SynthesisResult:
        # TODO should this also be cached?
        return self.inner_synthesizer.create_synthesis_result_from_wav(file, message, chunk_size)

