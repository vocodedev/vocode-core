from pydub import AudioSegment


class BaseSynthesizer:
    def synthesize(self, text) -> AudioSegment:
        raise NotImplementedError

    async def async_synthesize(self, text) -> AudioSegment:
        raise NotImplementedError
