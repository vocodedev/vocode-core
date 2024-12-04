from enum import Enum


class AudioEncoding(str, Enum):
    LINEAR16 = "linear16"
    MULAW = "mulaw"


class SamplingRate(int, Enum):
    RATE_8000 = 8000
    RATE_16000 = 16000
    RATE_22050 = 22050
    RATE_24000 = 24000
    RATE_44100 = 44100
    RATE_48000 = 48000
