import logging
import os
import wave

from vocode.streaming.input_device.silero_vad import SileroVAD
from vocode.streaming.transcriber import BaseTranscriber
from vocode.streaming.utils import prepare_audio_for_vad


class AudioStreamHandler:
    VAD_SAMPLE_RATE = 8000
    VAD_FRAME_SIZE = 256

    def __init__(self, conversation_id: str, transcriber: BaseTranscriber):
        self.conversation_id = conversation_id
        self.audio_buffer = []  # Buffer for storing audio chunks
        self.logger = logging.getLogger(__name__)  # Set up logging
        self.transcriber = transcriber
        self.audio_buffer_denoised = []
        self.frame_buffer = bytearray()
        if transcriber.transcriber_config.denoise:
            self.logger.info("Using Silero for VAD.")
            self.vad_wrapper = SileroVAD(sample_rate=self.VAD_SAMPLE_RATE, window_size=self.VAD_FRAME_SIZE)
        else:
            self.logger.info("Not using VAD.")
            self.vad_wrapper = None

    def receive_audio(self, chunk: bytes):
        # TODO: this might be blocking as hell(even though it is fast). Consider using a thread?
        if self.vad_wrapper is None:
            self.transcriber.send_audio(chunk)
        else:
            prepared_chunk = prepare_audio_for_vad(
                input_audio=chunk,
                input_sample_rate=self.transcriber.transcriber_config.input_device_config.sampling_rate,
                input_encoding=self.transcriber.transcriber_config.input_device_config.audio_encoding.value,
                output_sample_rate=self.VAD_SAMPLE_RATE,
            )
            self.frame_buffer.extend(prepared_chunk)
            while len(self.frame_buffer) >= self.VAD_FRAME_SIZE * 2:  # 2 bytes per 16-bit sample
                frame = self.frame_buffer[:self.VAD_FRAME_SIZE * 2]
                self.audio_buffer.append(frame)
                del self.frame_buffer[:self.VAD_FRAME_SIZE * 2]
                if self.vad_wrapper:
                    frame = self.vad_wrapper.process_chunk(frame)
                    self.audio_buffer_denoised.append(frame)

                self.transcriber.send_audio(frame)

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
