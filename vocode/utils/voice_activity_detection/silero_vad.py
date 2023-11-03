import logging
from typing import Optional

import numpy as np

from vocode.utils.voice_activity_detection.vad import BaseVoiceActivityDetector, BaseVoiceActivityDetectorConfig, \
    VoiceActivityDetectorType


class SileroVoiceActivityDetectorConfig(BaseVoiceActivityDetectorConfig, type=VoiceActivityDetectorType.SILERO.value):
    model_name: str = "silero_vad"
    USE_ONNX: bool = False
    repo_or_dir: str = 'snakers4/silero-vad'
    force_reload: str = True
    num_threads: int = 1
    threshold: float = .05
    model_save_path: str = "silero_vad.onnx"


class SileroVoiceActivityDetector(BaseVoiceActivityDetector[SileroVoiceActivityDetectorConfig]):
    def __init__(self, config: SileroVoiceActivityDetectorConfig, logger: Optional[logging.Logger] = None):
        import torch

        super().__init__(config, logger)
        if self.config.USE_ONNX:
            import onnxruntime

        self.torch = torch
        self.torch.set_num_threads(self.config.num_threads)

        self.model, self.utils = torch.hub.load(
            repo_or_dir=self.config.repo_or_dir,
            model=self.config.model_name,
            force_reload=self.config.force_reload,
            onnx=self.config.USE_ONNX,
        )
        (self.get_speech_timestamps,
         _,
         _,
         self.VADIterator,
         _) = self.utils
        self.vad_iterator = self.VADIterator(self.model)

    def is_voice_active(self, frame: bytes) -> bool:
        speech_timestamps = self.get_speech_timestamps(frame, self.model, sampling_rate=self.config.frame_rate)
        self.logger.debug(f"speech_timestamps = {speech_timestamps}")
        return np.mean(speech_timestamps) > self.config.threshold
