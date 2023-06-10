import io
import logging
from typing import Any, Optional, List
import aiohttp
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult, FillerAudio, TYPING_NOISE_PATH,
)
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils import convert_wav

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"

AUDIO_DATA_PRECACHE = {}


async def get_audio_data_map(
    phrase,
    voice_id,
    stability,
    similarity_boost,
    api_key,
    optimize_streaming_latency,
) -> List[FillerAudio]:
    key = (voice_id, phrase)
    cached = AUDIO_DATA_PRECACHE.get(key)
    if not cached:
        cached = await create_wav(
            message=BaseMessage(text=phrase),
            voice_id=voice_id,
            stability=stability,
            similarity_boost=similarity_boost,
            api_key=api_key,
            optimize_streaming_latency=optimize_streaming_latency,
        )
        AUDIO_DATA_PRECACHE[key] = cached
    return cached


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: ElevenLabsSynthesizerConfig,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(synthesizer_config)

        import elevenlabs

        self.elevenlabs = elevenlabs

        self.api_key = synthesizer_config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = synthesizer_config.voice_id or ADAM_VOICE_ID
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.words_per_minute = 150

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        fillers = []
        for phrase in self.synthesizer_config.filler_phrases:
            wav = await get_audio_data_map(
                phrase=phrase,
                voice_id=self.voice_id,
                stability=self.stability,
                similarity_boost=self.similarity_boost,
                api_key=self.api_key,
                optimize_streaming_latency=self.synthesizer_config.optimize_streaming_latency,
            )
            audio_data = convert_wav(
                wav,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=self.synthesizer_config.audio_encoding,
            )
            fillers.append(
                FillerAudio(
                    message=BaseMessage(text=phrase),
                    audio_data=audio_data,
                    synthesizer_config=self.synthesizer_config,
                    is_interruptible=True,
                    seconds_per_chunk=2,
                )
            )
        return fillers

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        output_bytes_io = await create_wav(
            message=message,
            voice_id=self.voice_id,
            stability=self.stability,
            similarity_boost=self.similarity_boost,
            api_key=self.api_key,
            optimize_streaming_latency=self.synthesizer_config.optimize_streaming_latency,
        )

        return self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )


async def create_wav(
        message: BaseMessage,
        voice_id: Optional[str] = None,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        api_key: Optional[str] = None,
        optimize_streaming_latency: Optional[int] = None,

) -> SynthesisResult:
    import elevenlabs
    voice = elevenlabs.Voice(voice_id=voice_id)
    if stability is not None and similarity_boost is not None:
        voice.settings = elevenlabs.VoiceSettings(
            stability=stability, similarity_boost=similarity_boost
        )
    url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key}
    body = {
        "text": message.text,
        "voice_settings": voice.settings.dict() if voice.settings else None,
    }
    if optimize_streaming_latency:
        body[
            "optimize_streaming_latency"
        ] = optimize_streaming_latency

    async with aiohttp.ClientSession() as session:
        async with session.request(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if not response.ok:
                raise Exception(
                    f"ElevenLabs API returned {response.status} status code"
                )
            audio_data = await response.read()
            audio_segment: AudioSegment = AudioSegment.from_mp3(
                io.BytesIO(audio_data)  # type: ignore
            )

            output_bytes_io = io.BytesIO()

            audio_segment.export(output_bytes_io, format="wav")  # type: ignore

            return output_bytes_io
