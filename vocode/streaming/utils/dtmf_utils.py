from enum import Enum

import numpy as np


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
}


def generate_dtmf_tone(
    keypad_entry: KeypadEntry, sampling_rate: int, duration_seconds: float = 0.3
) -> bytes:
    f1, f2 = DTMF_FREQUENCIES[keypad_entry]
    t = np.linspace(0, duration_seconds, int(sampling_rate * duration_seconds), endpoint=False)
    tone = np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t)
    tone = tone / np.max(np.abs(tone))  # Normalize to [-1, 1]
    return (tone * 32767).astype(np.int16).tobytes()
