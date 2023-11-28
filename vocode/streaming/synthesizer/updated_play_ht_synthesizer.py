import io
import logging
import os
from collections import defaultdict
from typing import Optional, Dict, List

from aiohttp import ClientSession
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import UpdatedPlayHtSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer, FillerAudio, FILLER_PHRASES,
)
from vocode.streaming.utils import convert_wav
from vocode.streaming.utils.mp3_helper import decode_mp3


class UpdatedPlayHtSynthesizer(BaseSynthesizer[UpdatedPlayHtSynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: UpdatedPlayHtSynthesizerConfig,
            logger: Optional[logging.Logger] = None,
            aiohttp_session: Optional[ClientSession] = None,
    ):
        import pyht
        self.pyht = pyht
        super().__init__(synthesizer_config, logger, aiohttp_session)
        self.synthesizer_config = synthesizer_config
        self.api_key = synthesizer_config.api_key or getenv("PLAY_HT_API_KEY")
        self.user_id = synthesizer_config.user_id or getenv("PLAY_HT_USER_ID")
        if not self.api_key or not self.user_id:
            raise ValueError(
                "You must set the PLAY_HT_API_KEY and PLAY_HT_USER_ID environment variables"
            )
        self.words_per_minute = 150
        self.experimental_streaming = synthesizer_config.experimental_streaming

        self.client = self.pyht.Client(
            user_id=self.user_id,
            api_key=self.api_key,
        )

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.create_total",
        )

        options = self.create_options()

        print(message.text)
        # for chunk in self.client.tts(message.text, options):
        #     print(chunk)
        # do something with the audio chunk
        # print(type(chunk))
        # output_bytes_io = decode_mp3(chunk)
        # result = self.create_synthesis_result_from_wav(
        #     synthesizer_config=self.synthesizer_config,
        #     file=output_bytes_io,
        #     message=message,
        #     chunk_size=chunk_size,
        # )
        # return result

        stream = self.client.tts(message.text, options)
        return SynthesisResult(
            self.experimental_mp3_streaming_output_generator(
                stream, chunk_size, create_speech_span
            ),  # should be wav
            lambda seconds: self.get_message_cutoff_from_voice_speed(
                message, seconds, self.words_per_minute
            ),
        )

    def create_options(self):
        options = self.pyht.TTSOptions(voice=self.synthesizer_config.voice_id)
        options.sample_rate = self.synthesizer_config.sampling_rate
        options.quality = self.synthesizer_config.quality
        options.temperature = self.synthesizer_config.temperature
        options.top_p = self.synthesizer_config.top_p
        options.speed = self.synthesizer_config.speed
        return options

    #     in_stream, out_stream = self.client.get_stream_pair(options)
    #     audio_task = asyncio.create_task(self.send_message_to_output(out_stream, message, chunk_size))

    #     print('#$@!'*10)
    #     print(message.text)
    #     print('#$@!'*10)

    #     await in_stream(*message.text)
    #     await in_stream.done()

    #     await asyncio.wait_for(audio_task, 60)

    # async def send_message_to_output(self, data: AsyncGenerator[bytes, None] | AsyncIterable[bytes], message: BaseMessage, chunk_size: int):
    #     for chunk in data:

    #         output_bytes_io = decode_mp3(chunk)

    #         result = self.create_synthesis_result_from_wav(
    #             synthesizer_config=self.synthesizer_config,
    #             file=output_bytes_io,
    #             message=message,
    #             chunk_size=chunk_size,
    #         )
    #         return result
    #     await asyncio.sleep(0.1)
    async def send_chunks(self, response, miniaudio_worker):

        while True:
            try:
                stream = self.async_response(response)
                chunk = await anext(stream)
                # print(chunk)
                miniaudio_worker.consume_nonblocking(chunk)
            except StopAsyncIteration:
                miniaudio_worker.consume_nonblocking(None)
                break

    @staticmethod
    async def async_response(response):
        for i in response:
            yield i

    async def get_phrase_filler_audios(self) -> Dict[str, List[FillerAudio]]:
        self.logger.debug("generating filler audios")
        filler_phrase_audios = defaultdict(list)
        for emotion, filler_phrases in FILLER_PHRASES.items():
            audios = await self.get_audios_from_messages(filler_phrases, self.base_filler_audio_path)
            filler_phrase_audios[emotion] = audios
        return filler_phrase_audios

    async def get_audios_from_messages(self, phrases: List[BaseMessage], base_path: str):
        audios = []
        for phrase in phrases:
            if not os.path.exists(base_path):
                os.makedirs(base_path)

            audio_path = await self.get_audio_data_from_cache_or_download(phrase, base_path)
            audio = FillerAudio(phrase,
                                audio_data=convert_wav(
                                    audio_path,
                                    output_sample_rate=self.synthesizer_config.sampling_rate,
                                    output_encoding=self.synthesizer_config.audio_encoding, ),
                                synthesizer_config=self.synthesizer_config,
                                is_interruptable=True,
                                seconds_per_chunk=2, )
            audios.append(audio)
        return audios

    async def get_audio_data_from_cache_or_download(self, phrase: BaseMessage, base_path: str) -> str:
        cache_key = "-".join(
            (
                str(phrase.text),
                str(self.synthesizer_config.type),
                str(self.synthesizer_config.audio_encoding),
                str(self.synthesizer_config.sampling_rate),
                str(self.synthesizer_config.voice_id),
            )
        )
        filler_audio_path = os.path.join(base_path, f"{cache_key}.wav")
        if not os.path.exists(filler_audio_path):
            self.logger.debug(f"Generating cached audio for {phrase.text}")
            audio_data = await self.download_filler_audio_data(phrase)

            with open(filler_audio_path, mode='bx') as f:
                f.write(audio_data)
        return filler_audio_path

    async def download_filler_audio_data(self, back_tracking_phrase):
        audio_data = b''
        options = self.create_options()
        for chunk in self.client.tts(back_tracking_phrase.text, options):
            audio_data += chunk

        return audio_data
