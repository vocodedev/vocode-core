import logging
import os
import wave

from vocode.streaming.input_device.rnn_noise import RNNoiseWrapper
from vocode.streaming.transcriber import BaseTranscriber
from vocode.streaming.utils import prepare_audio_for_rnnnoise


class AudioStreamHandler:
    FRAME_SIZE = 480

    def __init__(self, conversation_id: str, transcriber: BaseTranscriber):
        self.conversation_id = conversation_id
        self.audio_buffer = []  # Buffer for storing audio chunks
        self.logger = logging.getLogger(__name__)  # Set up logging
        self.transcriber = transcriber
        self.audio_buffer_denoised = []
        self.frame_buffer = bytearray()
        if transcriber.transcriber_config.denoise:
            self.logger.info("Using RNNoise for denoising.")
            self.rnnoise_wrapper = RNNoiseWrapper()
        else:
            self.logger.info("Not denoising audio.")
            self.rnnoise_wrapper = None

    def receive_audio(self, chunk: bytes):
        # TODO: this might be blocking as hell(even though it is fast). Consider using a thread?
        if self.rnnoise_wrapper is None:
            self.transcriber.send_audio(chunk)
        else:
            prepared_chunk = prepare_audio_for_rnnnoise(
                input_audio=chunk,
                input_sample_rate=self.transcriber.transcriber_config.input_device_config.sampling_rate,
                input_encoding=self.transcriber.transcriber_config.input_device_config.audio_encoding.value,
            )
            self.frame_buffer.extend(prepared_chunk)

            while len(self.frame_buffer) >= self.FRAME_SIZE * 2:  # 2 bytes per 16-bit sample
                # Extract a full frame from the buffer
                frame = self.frame_buffer[:self.FRAME_SIZE * 2]
                self.audio_buffer.append(frame)
                del self.frame_buffer[:self.FRAME_SIZE * 2]

                if self.rnnoise_wrapper:
                    # Process the frame
                    frame, vad_prob = self.rnnoise_wrapper.process_frame(frame)
                    # Store the denoised frame
                    self.audio_buffer_denoised.append(frame)

                # Store the frame (denoised or original) and send it for transcription
                self.transcriber.send_audio(frame)

    def __save_audio(self, audio_buffer, output_path):
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
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