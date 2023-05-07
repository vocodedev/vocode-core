from pydub import AudioSegment
from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber
import speech_recognition as sr

class SpeechRecognitionTranscriber(BaseTranscriber):
    def transcribe(self, audio_segment: AudioSegment) -> str:
        # Convert the audio segment to raw audio data
        audio_data = audio_segment.raw_data
        
        audio = sr.AudioData(audio_data, sample_rate=audio_segment.frame_rate, sample_width=audio_segment.sample_width)
        
        # Create a recognizer object
        r = sr.Recognizer()

        # Use the recognize_google method to transcribe the speech
        text = r.recognize_google(audio)

        return text