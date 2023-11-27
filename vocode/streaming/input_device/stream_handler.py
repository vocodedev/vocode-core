import logging
import os
import wave

from vocode.streaming.input_device.rnn_noise import RNNoiseWrapper
from vocode.streaming.transcriber import BaseTranscriber


class AudioStreamHandler:
    FRAME_SIZE = 480

    def __init__(self, transcriber: BaseTranscriber):
        self.audio_buffer = []  # Buffer for storing audio chunks
        self.logger = logging.getLogger(__name__)  # Set up logging
        self.transcriber = transcriber
        self.audio_buffer_denoised = []
        self.frame_buffer = bytearray()
        transcriber.transcriber_config.denoise = True
        if transcriber.transcriber_config.denoise:
            self.logger.info("Using RNNoise for denoising.")
            self.rnnoise_wrapper = RNNoiseWrapper()
        else:
            self.logger.info("Not denoising audio.")
            self.rnnoise_wrapper = None

    def receive_audio(self, chunk: bytes):
        self.frame_buffer.extend(chunk)
        # Optionally log the size of the incoming audio chunk
        self.logger.debug(f"Received audio chunk of size: {len(chunk)}")

        while len(self.frame_buffer) >= self.FRAME_SIZE * 2:  # 2 bytes per 16-bit sample
            # Extract a full frame from the buffer
            frame = self.frame_buffer[:self.FRAME_SIZE * 2]
            del self.frame_buffer[:self.FRAME_SIZE * 2]

            if self.rnnoise_wrapper:
                # Process the frame
                frame, vad_prob = self.rnnoise_wrapper.process_frame(frame)
                # Log VAD probability
                # Store the denoised frame
                self.audio_buffer_denoised.append(frame)

            # Store the frame (denoised or original) and send it for transcription
            self.audio_buffer.append(frame)
            self.transcriber.send_audio(frame)

    def __save_audio(self, audio_buffer, output_path):
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b''.join(audio_buffer))

    def flush(self, output_path: str):
        # Save the audio buffer to a file
        self.__save_audio(self.audio_buffer, output_path + ".wav")
        # Optionally log the flush action
        full_path = os.path.abspath(output_path)
        self.logger.info(f"Flushed audio buffer to {full_path}")
        # Clear the buffer after flushing
        self.audio_buffer = []

        # Save the denoised audio buffer to a file
        if len(self.audio_buffer_denoised) > 0:
            self.__save_audio(self.audio_buffer_denoised, output_path + "_denoised.wav")
            self.logger.info(f"Flushed audio for denoised.")
            self.audio_buffer_denoised = []

