import io
import logging

import numpy as np
import torch
from scipy.io.wavfile import write


class SileroVAD:
    INT16_NORM_CONST = 32768.0

    def __init__(
        self,
        sample_rate: int,
        window_size: int,
        threshold: float = 0.5,
        soft_threshold: float = 0.2,
        use_onnx: bool = False
    ):
        # Silero VAD is optimized for performance on single CPU thread
        torch.set_num_threads(1)

        model, (*_, VADIterator, _) = torch.hub.load(
            # TODO: load from local
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=True,
            onnx=use_onnx
        )
        self.model = model
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.soft_threshold = soft_threshold
        self.window_size = window_size
        self.logger = logging.getLogger(__name__)  # Set up logging

    def process_chunk(self, chunk: bytes) -> bytes:
        chunk_array = torch.frombuffer(chunk, dtype=torch.int16).to(torch.float32) / self.INT16_NORM_CONST
        chunk_array_len = len(chunk_array)

        # Run VAD on chunks of data
        mask = np.zeros(chunk_array_len)
        for i in range(0, chunk_array_len, self.window_size):
            frame = chunk_array[i:i + self.window_size]
            if len(frame) < self.window_size:
                break
            speech_prob = self.model(frame, self.sample_rate).item()
            if speech_prob > self.threshold:
                mask[i:i + self.window_size] = 1.0
            elif speech_prob > self.soft_threshold:
                # Soft mask to make transitions smoother
                # and avoid cutting off speech segments
                mask[i:i + self.window_size] = speech_prob

        # Mask audio chunk and convert back to bytes
        masked_chunk = chunk_array.numpy() * mask
        chunk_array = (masked_chunk * self.INT16_NORM_CONST).astype(np.int16)
        bytes_wav = bytes()
        byte_io = io.BytesIO(bytes_wav)
        write(byte_io, self.sample_rate, chunk_array)
        chunk_bytes = byte_io.read()[-len(chunk):]

        return chunk_bytes

    def reset_states(self) -> None:
        self.model.reset_states()
