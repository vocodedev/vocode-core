import asyncio
import logging
import queue
from typing import Optional
import threading

from azure.cognitiveservices.speech.audio import AudioInputStream, PushAudioInputStream, AudioStreamFormat, \
    AudioStreamWaveFormat

from vocode import getenv

from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.transcriber.base_transcriber import (
    BaseTranscriber,
    Transcription,
)
from vocode.streaming.models.transcriber import AzureTranscriberConfig
from vocode.streaming.utils import create_loop_in_thread

class AzureTranscriber(BaseTranscriber):

    def __init__(
            self,
            transcriber_config: AzureTranscriberConfig,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(transcriber_config)
        self.logger = logger

        format = None
        if self.transcriber_config.audio_encoding == AudioEncoding.LINEAR16:

            format = AudioStreamFormat(
                samples_per_second=self.transcriber_config.sampling_rate,
                wave_stream_format=AudioStreamWaveFormat.PCM
            )

        elif self.transcriber_config.audio_encoding == AudioEncoding.MULAW:
            format = AudioStreamFormat(
                samples_per_second=self.transcriber_config.sampling_rate,
                wave_stream_format=AudioStreamWaveFormat.MULAW
            )

        import azure.cognitiveservices.speech as speechsdk

        self.push_stream = PushAudioInputStream(format)

        config = speechsdk.audio.AudioConfig(stream=self.push_stream)

        speech_config = speechsdk.SpeechConfig(subscription=getenv("AZURE_SPEECH_KEY"),
                                               region=getenv("AZURE_SPEECH_REGION"))

        self.speech = speechsdk.SpeechRecognizer(speech_config=speech_config,
                                                 audio_config=config)

        self._queue = queue.Queue()
        self._ended = False
        self.is_ready = False
        self.event_loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            name="azure_transcriber",
            target=create_loop_in_thread,
            args=(self.event_loop, self.process()),
        )

    async def run(self):
        self.thread.start()

    async def recognized_sentence_final(self, evt):
        await self.on_response(
            Transcription(evt.result.text, 1.0, True)
        )

    async def recognized_sentence_stream(self, evt):
        await self.on_response(
            Transcription(evt.result.text, 1.0, False)
        )

    async def process(self):
        stream = self.generator()

        def stop_cb(evt):
            self.logger.debug('CLOSING on {}'.format(evt))
            self.speech.stop_continuous_recognition()
            self._ended = True

        self.speech.recognizing.connect(lambda x: asyncio.run(self.recognized_sentence_stream(x)))
        self.speech.recognized.connect(lambda x: asyncio.run(self.recognized_sentence_final(x)))
        self.speech.session_started.connect(lambda evt: self.logger.debug('SESSION STARTED: {}'.format(evt)))
        self.speech.session_stopped.connect(lambda evt: self.logger.debug('SESSION STOPPED {}'.format(evt)))
        self.speech.canceled.connect(lambda evt: self.logger.debug('CANCELED {}'.format(evt)))

        self.speech.session_stopped.connect(stop_cb)
        self.speech.canceled.connect(stop_cb)
        self.speech.start_continuous_recognition_async()

        for content in stream:
            self.push_stream.write(content)

    def terminate(self):
        self._ended = True

    def send_audio(self, chunk: bytes):
        self._queue.put_nowait(chunk)

    async def process_responses_loop(self, responses):
        for response in responses:
            await self._on_response(response)

            if self._ended:
                break

    async def _on_response(self, response):
        if not response.results:
            return

        result = response.results[0]
        if not result.alternatives:
            return

        top_choice = result.alternatives[0]
        message = top_choice.transcript
        confidence = top_choice.confidence

        return await self.on_response(
            Transcription(message, confidence, result.is_final)
        )

    def generator(self):
        while not self._ended:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._queue.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._queue.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)
