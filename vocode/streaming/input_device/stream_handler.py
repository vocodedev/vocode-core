import logging
import os
import wave
from concurrent.futures import ThreadPoolExecutor
import asyncio
import numpy as np

from vocode.streaming.input_device.silero_vad import SileroVAD
from vocode.streaming.transcriber import BaseTranscriber
from vocode.streaming.utils import prepare_audio_for_vad


class AudioStreamHandler:
    VAD_SAMPLE_RATE = 8000
    VAD_FRAME_SIZE = 512
    VAD_SPEECH_PAD_MS = 192
    VAD_SPEECH_MIN_DURATION_MS = 64

    def __init__(self, conversation_id: str, transcriber: BaseTranscriber):
        self.conversation_id = conversation_id
        self.audio_buffer = []  # Buffer for storing audio chunks
        self.logger = logging.getLogger(__name__)  # Set up logging
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.transcriber = transcriber
        self.audio_buffer_denoised = []
        self.frame_buffer = bytearray()
        if transcriber.transcriber_config.vad:
            self.logger.info("Using Silero for VAD.")
            self.vad_wrapper = SileroVAD(
                sample_rate=self.VAD_SAMPLE_RATE,
                window_size=self.VAD_FRAME_SIZE,
            )
            speech_pad_samples = int(self.VAD_SAMPLE_RATE * self.VAD_SPEECH_PAD_MS / 1000) * 2
            speech_min_samples = int(self.VAD_SAMPLE_RATE * self.VAD_SPEECH_MIN_DURATION_MS / 1000) * 2
            self.speech_pad_frames = int(speech_pad_samples / self.VAD_FRAME_SIZE)
            self.speech_min_frames = int(speech_min_samples / self.VAD_FRAME_SIZE)
            self.padding_frames_left = 0
            self.offset_samples = speech_pad_samples + speech_min_samples
            self.frame_buffer_is_speech = np.zeros(self.speech_pad_frames + self.speech_min_frames).astype(np.bool_)
        else:
            self.logger.info("Not using VAD.")
            self.vad_wrapper = None
        self.vad_triggered = False

    async def post_init(self):
        self.logger.info("Loading VAD model...")
        if self.vad_wrapper is not None:
            loop = asyncio.get_running_loop()
            self.vad_wrapper.model = await loop.run_in_executor(
                self.executor,
                self.vad_wrapper.load_model
            )

    async def receive_audio(self, chunk: bytes):
        if self.vad_wrapper is None:
            self.transcriber.send_audio(chunk)
        else:
            # Run prepare_audio_for_vad in the executor
            loop = asyncio.get_running_loop()
            prepared_chunk = await loop.run_in_executor(
                self.executor,
                prepare_audio_for_vad,
                chunk,
                self.transcriber.transcriber_config.input_device_config.sampling_rate,
                self.VAD_SAMPLE_RATE,
                self.transcriber.transcriber_config.input_device_config.audio_encoding.value,
            )
            self.frame_buffer.extend(prepared_chunk)
            await self.process_frame_buffer()

    async def process_frame_buffer(self) -> None:
        loop = asyncio.get_running_loop()
        while len(self.frame_buffer) >= self.VAD_FRAME_SIZE + self.offset_samples:  # 2 bytes per 16-bit sample
            frame_to_process = self.frame_buffer[self.offset_samples:self.offset_samples + self.VAD_FRAME_SIZE]
            is_speech = await loop.run_in_executor(self.executor, self.vad_wrapper.process_chunk, frame_to_process)
            if is_speech:
                if self.speech_min_frames < 2 or self.frame_buffer_is_speech[-(self.speech_min_frames - 1):].all():
                    # If the speech segment is long enough, trigger VAD and pad preceding frames with ones
                    self.frame_buffer_is_speech[-(self.speech_pad_frames + self.speech_min_frames):] = True
                    self.padding_frames_left = self.speech_pad_frames
                    self.vad_triggered = True
                else:
                    self.vad_triggered = False
                self.frame_buffer_is_speech = np.concatenate([self.frame_buffer_is_speech, [True]])
            else:
                if self.vad_triggered and self.padding_frames_left > 0:
                    # If VAD is triggered, pad the following speech frames with ones
                    self.frame_buffer_is_speech = np.concatenate([self.frame_buffer_is_speech, [True]])
                    self.padding_frames_left -= 1
                else:
                    self.vad_triggered = False
                    self.frame_buffer_is_speech = np.concatenate([self.frame_buffer_is_speech, [False]])

            # Remove speech segments shorter than minimal required duration
            if self.speech_min_frames > 1:
                frame_buffer_is_speech_filtered = self._remove_short_speech_segments(self.frame_buffer_is_speech)
            else:
                frame_buffer_is_speech_filtered = self.frame_buffer_is_speech

            frame_to_send = self.frame_buffer[:self.VAD_FRAME_SIZE]
            self.audio_buffer.append(frame_to_send)
            del self.frame_buffer[:self.VAD_FRAME_SIZE]

            if not frame_buffer_is_speech_filtered[0]:
                frame_to_send = bytearray(len(frame_to_send))
            self.frame_buffer_is_speech = self.frame_buffer_is_speech[1:]
            self.audio_buffer_denoised.append(frame_to_send)
            self.transcriber.send_audio(frame_to_send)

    def _remove_short_speech_segments(self, frame_buffer: np.array) -> np.array:
        """Remove detected speech frames shorter than minimal required duration"""
        result = np.zeros(self.speech_pad_frames + 1).astype(np.bool_)
        frame_buffer_windows = np.lib.stride_tricks.as_strided(
            frame_buffer,
            shape=(frame_buffer.size - (self.speech_min_frames - 1), self.speech_min_frames),
            strides=(1, 1)
        )
        for i in np.where(frame_buffer_windows.all(axis=1))[0]:
            result[i:i + self.speech_min_frames] = True
        return result

    def __save_audio(self, audio_buffer, output_path):
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(b''.join(audio_buffer))

    def save_debug_audios(self):
        output_path = os.environ.get("DEBUG_AUDIO_PATH", None)
        if not output_path:
            self.logger.info("DEBUG_AUDIO_PATH not set, not saving debug audios.")
            return

        if not os.path.exists(output_path):
            os.mkdir(output_path)

        # Save the audio buffer to a file if it doesn't exist
        raw_output_path = output_path + f"/{self.conversation_id}_raw.wav"
        if not os.path.exists(raw_output_path):
            self.__save_audio(self.audio_buffer, raw_output_path)
            self.logger.info(f"Saved {raw_output_path}")
        else:
            self.logger.info(f"File {raw_output_path} already exists, not overwriting.")

        # Save the denoised audio buffer to a file if it doesn't exist
        if len(self.audio_buffer_denoised) > 0:
            denoised_output_path = output_path + f"/{self.conversation_id}_denoised.wav"
            if not os.path.exists(denoised_output_path):
                self.__save_audio(self.audio_buffer_denoised, denoised_output_path)
                self.logger.info(f"Saved {denoised_output_path}.")
            else:
                self.logger.info(f"File {denoised_output_path} already exists, not overwriting.")

    def terminate(self):
        self.executor.shutdown(wait=False)
