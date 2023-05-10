import queue
import threading
import sounddevice as sd
import numpy as np

from vocode.streaming.telephony.constants import DEFAULT_CHUNK_SIZE

from .base_output_device import BaseOutputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding


class SpeakerOutput(BaseOutputDevice):
    DEFAULT_SAMPLING_RATE = 44100

    def __init__(
        self,
        device_info: dict,
        sampling_rate: int = None,
        audio_encoding: AudioEncoding = AudioEncoding.LINEAR16,
    ):
        self.device_info = device_info
        sampling_rate = sampling_rate or int(
            self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE)
        )
        super().__init__(sampling_rate, audio_encoding)
        self.stream = sd.OutputStream(
            channels=1,
            samplerate=self.sampling_rate,
            dtype=np.int16,
            blocksize=44100,
            device=int(self.device_info["index"]),
            callback=self.callback,
        )
        self.stream.start()
        self.queue: queue.Queue[np.ndarray] = queue.Queue()

    def callback(self, outdata: np.ndarray, frames, time, status):
        if self.queue.empty():
            return
        data = self.queue.get()
        outdata[: data.shape[0], 0] = data
        if data.shape[0] < frames:  # If the data chunk is smaller than the blocksize
            outdata[data.shape[0] :] = 0

    async def send_async(self, chunk):
        chunk_arr = np.frombuffer(chunk, dtype=np.int16)
        for i in range(0, self.stream.blocksize, chunk_arr.shape[0]):
            self.queue.put_nowait(chunk_arr[i : i + self.stream.blocksize])

    def terminate(self):
        self.stream.close()

    @classmethod
    def from_default_device(
        cls,
        sampling_rate: int = None,
    ):
        return cls(sd.query_devices(kind="output"), sampling_rate)
