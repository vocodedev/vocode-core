import logging
from typing import Generic, TypeVar, Optional

from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig

NoiseCancelingConfigType = TypeVar("NoiseCancelingConfigType", bound=NoiseCancelingConfig)


class BaseNoiseCanceler(Generic[NoiseCancelingConfigType]):
    def __init__(self, noise_canceling_config: NoiseCancelingConfigType, logger: Optional[logging.Logger] = None):
        self.noise_canceling_config = noise_canceling_config
        self.logger = logger

    def get_noise_canceling_config(self) -> NoiseCancelingConfig:
        return self.noise_canceling_config

    def cancel_noise(self, audio: bytes) -> bytes:
        raise NotImplementedError
