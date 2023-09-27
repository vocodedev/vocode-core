from enum import Enum

from vocode.streaming.models.model import TypedModel


class NoiseCancelingType(str, Enum):
    BASE = "base_noise_canceling"
    PICO_VOICE = "pico_voice_noise_cancelling"
    NOISE_REDUCE = "noise_reduce_noise_cancelling"


class NoiseCancelingConfig(TypedModel, type=NoiseCancelingType.BASE.value):
    sample_rate: int = 8000
