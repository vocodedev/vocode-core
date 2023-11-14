import logging
import queue
import threading
import time
from typing import Optional

from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.transcriber import GoogleTranscriberConfig
from vocode.streaming.transcriber.base_transcriber import (
    BaseThreadAsyncTranscriber,
    Transcription,
)


# TODO: make this nonblocking so it can run in the main thread, see speech.async_client.SpeechAsyncClient
class GoogleTranscriber(BaseThreadAsyncTranscriber[GoogleTranscriberConfig]):
    def __init__(
            self,
            transcriber_config: GoogleTranscriberConfig,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(transcriber_config)

        from google.cloud import speech
        import google.auth

        google.auth.default()
        self.speech = speech
        self.logger = logger

        self._ended = False
        self.google_streaming_config = self.create_google_streaming_config()
        self.client = self.speech.SpeechClient()
        self.start_time = None
        self.is_ready = False
        self.restart_event = threading.Event()
        if self.transcriber_config.endpointing_config:
            raise Exception("Google endpointing config not supported yet")

    def create_google_streaming_config(self):
        extra_params = {}
        if self.transcriber_config.model:
            extra_params["model"] = self.transcriber_config.model
            extra_params["use_enhanced"] = True

        if self.transcriber_config.language_code:
            extra_params["language_code"] = self.transcriber_config.language_code

        if self.transcriber_config.audio_encoding == AudioEncoding.LINEAR16:
            google_audio_encoding = self.speech.RecognitionConfig.AudioEncoding.LINEAR16
        elif self.transcriber_config.audio_encoding == AudioEncoding.MULAW:
            google_audio_encoding = self.speech.RecognitionConfig.AudioEncoding.MULAW

        return self.speech.StreamingRecognitionConfig(
            config=self.speech.RecognitionConfig(
                encoding=google_audio_encoding,
                sample_rate_hertz=self.transcriber_config.sampling_rate,
                **extra_params
            ),
            interim_results=True,
        )

    def _run_loop(self):
        self.logger.info("Transcriber loop started")
        while not self._ended:
            self.start_time = time.time()
            self.restart_stream()
            self.restart_event.wait()
            self.restart_event.clear()

    def restart_stream(self):
        self.logger.info("Transcriber stream restarted or started")
        self.client = self.speech.SpeechClient()
        stream = self.generator()
        self.logger.info("Started new STT generator")
        requests = (self.speech.StreamingRecognizeRequest(audio_content=content) for content in stream)
        responses = self.client.streaming_recognize(self.google_streaming_config, requests)
        self.process_responses_loop(responses)

    def terminate(self):
        self._ended = True
        super().terminate()

    def process_responses_loop(self, responses):
        for response in responses:
            self._on_response(response)

            if self._ended:
                break

    def _on_response(self, response):
        if not response.results:
            return

        result = response.results[0]
        if not result.alternatives:
            return

        top_choice = result.alternatives[0]
        message = top_choice.transcript
        confidence = top_choice.confidence

        self.output_janus_queue.sync_q.put_nowait(
            Transcription(
                message=message, confidence=confidence, is_final=result.is_final
            )
        )

    def generator(self):
        self.logger.info("Starting STT generator")
        while not self._ended:
            if time.time() - self.start_time > 250:  # 250 seconds limit, before restarting.
                self.logger.warning(f"Killing generator to restart, hit limit of 250 seconds.")
                self.restart_event.set()
                return
            chunk = self.input_janus_queue.sync_q.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self.input_janus_queue.sync_q.get_nowait()
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b"".join(data)
