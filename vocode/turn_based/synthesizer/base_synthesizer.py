from pydub import AudioSegment


class BaseSynthesizer:
    def synthesize(self, text) -> AudioSegment:
        raise NotImplementedError
