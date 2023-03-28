from enum import Enum


class AudioEncoding(str, Enum):
    LINEAR16 = "linear16"
    MULAW = "mulaw"
