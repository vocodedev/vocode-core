from pydub import AudioSegment


class BaseOutputDevice:
    def send_audio(self, audio: AudioSegment) -> None:
        raise NotImplementedError

    def terminate(self):
        pass
