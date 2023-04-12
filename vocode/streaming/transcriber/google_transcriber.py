import asyncio
import logging
import os
import time
import queue
from typing import Optional
from google.cloud import speech
import threading
from vocode import getenv

from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.transcriber.base_transcriber import (
    BaseTranscriber,
    Transcription,
)
from vocode.streaming.models.transcriber import GoogleTranscriberConfig
from vocode.streaming.utils import create_loop_in_thread


class GoogleTranscriber(BaseTranscriber):
    def __init__(
        self,
        transcriber_config: GoogleTranscriberConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(transcriber_config)
        self._queue = queue.Queue()
        self._ended = False
        credentials_path = getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise Exception(
                "Please set GOOGLE_APPLICATION_CREDENTIALS environment variable"
            )
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        self.google_streaming_config = self.create_google_streaming_config()
        self.client = speech.SpeechClient()
        self.is_ready = False
        if self.transcriber_config.endpointing_config:
            raise Exception("Google endpointing config not supported yet")
        self.event_loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            name="google_transcriber",
            target=create_loop_in_thread,
            args=(self.event_loop, self.process()),
        )

    def create_google_streaming_config(self):
        extra_params = {}
        if self.transcriber_config.model:
            extra_params["model"] = self.transcriber_config.model
            extra_params["use_enhanced"] = True

        if self.transcriber_config.audio_encoding == AudioEncoding.LINEAR16:
            google_audio_encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
        elif self.transcriber_config.audio_encoding == AudioEncoding.MULAW:
            google_audio_encoding = speech.RecognitionConfig.AudioEncoding.MULAW

        return speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=google_audio_encoding,
                sample_rate_hertz=self.transcriber_config.sampling_rate,
                language_code="en-US",
                **extra_params
            ),
            interim_results=True,
        )

    async def run(self):
        self.thread.start()

    async def process(self):
        stream = self.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in stream
        )
        responses = self.client.streaming_recognize(
            self.google_streaming_config, requests
        )
        await self.process_responses_loop(responses)

    def terminate(self):
        self._ended = True

    def send_audio(self, chunk: bytes):
        self._queue.put(chunk, block=False)

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
