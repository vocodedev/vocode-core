import audioop
from enum import Enum
from typing import Dict, Tuple

import numpy as np

from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.utils.singleton import Singleton

DEFAULT_DTMF_TONE_LENGTH_SECONDS = 0.3
DEFAULT_DTMF_TONE_SILENCE_SECONDS = 0.1
MAX_INT = 32767


class KeypadEntry(str, Enum):
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    ZERO = "0"
    POUND = "#"
    STAR = "*"


DTMF_FREQUENCIES = {
    KeypadEntry.ONE: (697, 1209),
    KeypadEntry.TWO: (697, 1336),
    KeypadEntry.THREE: (697, 1477),
    KeypadEntry.FOUR: (770, 1209),
    KeypadEntry.FIVE: (770, 1336),
    KeypadEntry.SIX: (770, 1477),
    KeypadEntry.SEVEN: (852, 1209),
    KeypadEntry.EIGHT: (852, 1336),
    KeypadEntry.NINE: (852, 1477),
    KeypadEntry.ZERO: (941, 1336),
    KeypadEntry.STAR: (941, 1209),
    KeypadEntry.POUND: (941, 1477),
}


class DTMFToneGenerator(Singleton):

    def __init__(self):
        self.tone_cache: Dict[Tuple[KeypadEntry, int, AudioEncoding], bytes] = {}

    def generate(
        self,
        keypad_entry: KeypadEntry,
        sampling_rate: int,
        audio_encoding: AudioEncoding,
        duration_seconds: float = DEFAULT_DTMF_TONE_LENGTH_SECONDS,
        silence_seconds: float = DEFAULT_DTMF_TONE_SILENCE_SECONDS,
    ) -> bytes:
        if (keypad_entry, sampling_rate, audio_encoding) in self.tone_cache:
            return self.tone_cache[(keypad_entry, sampling_rate, audio_encoding)]
        f1, f2 = DTMF_FREQUENCIES[keypad_entry]
        t = np.linspace(0, duration_seconds, int(sampling_rate * duration_seconds), endpoint=False)
        tone = np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t)
        tone = tone / np.max(np.abs(tone))  # Normalize to [-1, 1]
        pcm = (tone * MAX_INT).astype(np.int16).tobytes()
        pcm += b"\0" * int(silence_seconds * sampling_rate * 2)
        if audio_encoding == AudioEncoding.MULAW:
            output = audioop.lin2ulaw(pcm, 2)
        else:
            output = pcm
        self.tone_cache[(keypad_entry, sampling_rate, audio_encoding)] = output
        return output
