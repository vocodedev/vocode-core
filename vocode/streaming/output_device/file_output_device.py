import wave
from asyncio import Queue
import asyncio
import numpy as np

from .base_output_device import BaseOutputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.utils.worker import ThreadAsyncWorker


class FileWriterWorker(ThreadAsyncWorker):
    def __init__(self, input_queue: Queue, wave) -> None:
        super().__init__(input_queue)
        self.wav = wave

    def _run_loop(self):
        while True:
            try:
                block = self.input_janus_queue.sync_q.get()
                self.wav.writeframes(block)
            except asyncio.CancelledError:
                return

    def terminate(self):
        super().terminate()
        self.wav.close()


class FileOutputDevice(BaseOutputDevice):
    DEFAULT_SAMPLING_RATE = 44100

    def __init__(
        self,
        file_path: str,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        audio_encoding: AudioEncoding = AudioEncoding.LINEAR16,
    ):
        super().__init__(sampling_rate, audio_encoding)
        self.blocksize = self.sampling_rate  # One second of audio data
        self.buffer = np.array([], dtype=np.int16)
        self.queue: Queue[np.ndarray] = Queue()

        wav = wave.open(file_path, "wb")
        wav.setnchannels(1)  # Mono channel
        wav.setsampwidth(2)  # 16-bit samples
        wav.setframerate(self.sampling_rate)
        self.wav = wav

        self.thread_worker = FileWriterWorker(self.queue, wav)
        self.thread_worker.start()

    def consume_nonblocking(self, chunk):
        chunk_arr = np.frombuffer(chunk, dtype=np.int16)
        self.buffer = np.concatenate([self.buffer, chunk_arr])
        while self.buffer.shape[0] >= self.blocksize:
            block = self.buffer[: self.blocksize]
            self.buffer = self.buffer[self.blocksize :]
            self.queue.put_nowait(block)

    def terminate(self):
        self.thread_worker.terminate()
