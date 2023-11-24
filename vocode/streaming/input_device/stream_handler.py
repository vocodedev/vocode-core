import logging
import wave

from vocode.streaming.input_device.rnn_noise import RNNoiseWrapper
from vocode.streaming.transcriber import BaseTranscriber


class AudioStreamHandler:

    def __init__(self, transcriber: BaseTranscriber):
        self.audio_buffer = []  # Buffer for storing audio chunks
        self.logger = logging.getLogger(__name__)  # Set up logging
        self.transcriber = transcriber
        if transcriber.transcriber_config.denoise:
            self.logger.info("Using RNNoise for denoising.")
            self.rnnoise_wrapper = RNNoiseWrapper()
        else:
            self.logger.info("Not denoising audio.")
            self.rnnoise_wrapper = None

    def receive_audio(self, chunk: bytes):
        # Optionally log the size of the incoming audio chunk
        self.logger.debug(f"Received audio chunk of size: {len(chunk)}")

        if self.rnnoise_wrapper:
            chunk, vad_prob = self.rnnoise_wrapper.process_frame(chunk)
            # Optionally log the voice activity probability
            self.logger.debug(f"VAD probability: {vad_prob}")

        # Store the (possibly denoised) chunk in the buffer
        self.audio_buffer.append(chunk)

        self.transcriber.send_audio(chunk)

    def flush(self, output_path: str):
        # Save the audio buffer to a file
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit samples
            wf.setframerate(48000)  # 48kHz sample rate
            wf.writeframes(b''.join(self.audio_buffer))
        # Optionally log the flush action
        self.logger.info(f"Flushed audio buffer to {output_path}")

        # Clear the buffer after flushing
        self.audio_buffer = []
