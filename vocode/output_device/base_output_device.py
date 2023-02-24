from ..models.audio_encoding import AudioEncoding

class BaseOutputDevice:

    def __init__(self, sampling_rate: int, audio_encoding: AudioEncoding):
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding

    async def send_async(self, chunk):
        raise NotImplemented

    async def maybe_send_mark_async(self, message):
        pass


