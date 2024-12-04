from pydub import AudioSegment


class BaseTranscriber:
    def transcribe(self, audio_segment: AudioSegment) -> str:
        raise NotImplementedError
