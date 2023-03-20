from pydub import AudioSegment


class BaseInputDevice:
    def start_listening(self):
        raise NotImplementedError

    def end_listening(self) -> AudioSegment:
        raise NotImplementedError
