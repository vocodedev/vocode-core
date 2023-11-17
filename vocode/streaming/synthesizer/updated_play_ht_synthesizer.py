import logging
from typing import Optional

from aiohttp import ClientSession

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import UpdatedPlayHtSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)


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

        options = self.pyht.TTSOptions(voice=self.synthesizer_config.voice_id)
        options.sample_rate = self.synthesizer_config.sample_rate
        options.quality = self.synthesizer_config.quality
        options.temperature = self.synthesizer_config.temperature
        options.top_p = self.synthesizer_config.top_p
        options.speed = self.synthesizer_config.speed

        
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
