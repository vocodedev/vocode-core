from gtts import gTTS
from pydub import AudioSegment
from io import BytesIO
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class GTTSSynthesizer(BaseSynthesizer):
    def synthesize(self, text) -> AudioSegment:
        tts = gTTS(text)
        audio_file = BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        return AudioSegment.from_mp3(audio_file)
