import asyncio
import io
import logging
from typing import Optional, List

from aiohttp import ClientSession, ClientTimeout
from pydub import AudioSegment
import requests
from opentelemetry.context.context import Context

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
    FILLER_PHRASES,
    FILLER_AUDIO_PATH,
    FillerAudio
)
from vocode.streaming.utils.mp3_helper import decode_mp3
from vocode.streaming.utils import convert_wav, get_chunk_size_per_second


TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtSynthesizer(BaseSynthesizer[PlayHtSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: PlayHtSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        self.synthesizer_config = synthesizer_config
        self.api_key = synthesizer_config.api_key or getenv("PLAY_HT_API_KEY")
        self.user_id = synthesizer_config.user_id or getenv("PLAY_HT_USER_ID")
        if not self.api_key or not self.user_id:
            raise ValueError(
                "You must set the PLAY_HT_API_KEY and PLAY_HT_USER_ID environment variables"
            )

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-User-ID": self.user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "voice": self.synthesizer_config.voice_id,
            "text": message.text,
            "sample_rate": self.synthesizer_config.sampling_rate,
        }
        if self.synthesizer_config.speed:
            body["speed"] = self.synthesizer_config.speed
        if self.synthesizer_config.seed:
            body["seed"] = self.synthesizer_config.seed
        if self.synthesizer_config.temperature:
            body["temperature"] = self.synthesizer_config.temperature

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.create_total",
        )

        async with self.aiohttp_session.post(
            TTS_ENDPOINT, headers=headers, json=body, timeout=ClientTimeout(total=15)
        ) as response:
            if not response.ok:
                raise Exception(f"Play.ht API error status code {response.status}")
            read_response = await response.read()
            create_speech_span.end()
            convert_span = tracer.start_span(
                f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.convert",
            )
            output_bytes_io = decode_mp3(read_response)

            result = self.create_synthesis_result_from_wav(
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )
            convert_span.end()
            return result

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        filler_phrase_audios = []
        for filler_phrase in FILLER_PHRASES:
            cache_key = "-".join(
                (
                    str(filler_phrase.text),
                    str(self.synthesizer_config.type),
                    str(self.synthesizer_config.audio_encoding),
                    str(self.synthesizer_config.sampling_rate),
                    str(self.synthesizer_config.voice_id),
                    str(self.synthesizer_config.speed)
                )
            )
            filler_audio_path = os.path.join(FILLER_AUDIO_PATH, f"{cache_key}.wav")
            

            if os.path.exists(filler_audio_path):
                audio_data = open(filler_audio_path, "rb").read()
            else:
                self.logger.debug(f"Generating filler audio for {filler_phrase.text}")

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "X-User-ID": self.user_id,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                }
                body = {
                    "voice": self.synthesizer_config.voice_id,
                    "text": filler_phrase.text,
                    "sample_rate": self.synthesizer_config.sampling_rate,
                }
                
                if self.synthesizer_config.speed: # is not None and self.similarity_boost is not None:
                    body["speed"] = self.synthesizer_config.speed
                if self.synthesizer_config.seed:
                    body["seed"] = self.synthesizer_config.seed
                if self.synthesizer_config.temperature:
                    body["temperature"] = self.synthesizer_config.temperature


                create_speech_span = tracer.start_span(
                            f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.create_total",
                        )
                
                async with self.aiohttp_session.post(
                            TTS_ENDPOINT, headers=headers, json=body, timeout=ClientTimeout(total=15)
                        ) as response:
                            if not response.ok:
                                raise Exception(f"Play.ht API error status code {response.status}")
                            audio_data = await response.read()
                            create_speech_span.end()


                            audio_segment: AudioSegment = AudioSegment.from_mp3(
                            io.BytesIO(audio_data)  # type: ignore
                        )

                            audio_segment.export(filler_audio_path, format="wav")

            filler_phrase_audios.append(
                FillerAudio(
                    filler_phrase,
                    audio_data=convert_wav(
                        filler_audio_path,
                        output_sample_rate=self.synthesizer_config.sampling_rate,
                        output_encoding=self.synthesizer_config.audio_encoding,
                    ),
                    synthesizer_config=self.synthesizer_config,
                    is_interruptable=True,
                    seconds_per_chunk=2,
                )
            )
        return filler_phrase_audios
