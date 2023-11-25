import logging
from datetime import datetime, timedelta
from typing import Optional
import time 

class VoiceActivityDetectorConfig:
    def __init__(self, min_activity_duration, speech_ratio):
        self.min_activity_duration = min_activity_duration
        self.speech_ratio = speech_ratio

class BaseVoiceActivityDetector:
    def __init__(self, config: VoiceActivityDetectorConfig, logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.config = config
        self.speech_start_timestamp = None
        self.activity_state = {True: 0, False: 0}
        self.is_interrupted = False

    def is_voice_active(self, frame: bytes) -> bool:
        # Simulated method, replace with actual implementation
        return len(frame) > 0

    def should_interrupt(self, is_voice_active: bool) -> bool:
        now = datetime.now()

        self.activity_state[is_voice_active] += 1

        if is_voice_active and self.speech_start_timestamp is None:
            self.activity_state = {True: 0, False: 0}
            self.speech_start_timestamp = now

        if self.speech_start_timestamp is None:
            return False

        if (now - self.speech_start_timestamp) > self.config.min_activity_duration:
            speech_ratio = self.activity_state[True] / (self.activity_state[True] + self.activity_state[False])
            print(speech_ratio)
            if speech_ratio > self.config.speech_ratio:
                if self.is_interrupted:
                    return False
                self.is_interrupted = True
                self.speech_start_timestamp = None
                return True
            else:
                self.is_interrupted = False
                self.speech_start_timestamp = None
                return False

# Testing the should_interrupt method logic
def test_should_interrupt_logic(detector, voice_activity_states):
    for is_voice_active in voice_activity_states:
        result = detector.should_interrupt(is_voice_active)
        print(f"Is Voice Active: {is_voice_active}, Should Interrupt: {result}")
        time.sleep(0.1)
# Example usage
if __name__ == "__main__":
    # Configure the VAD
    vad_config = VoiceActivityDetectorConfig(min_activity_duration=timedelta(milliseconds=300), speech_ratio=0.8)
    vad = BaseVoiceActivityDetector(config=vad_config)

    # Simulate voice activity states (replace with actual data)
    voice_activity_states = [
        True, True, True, True, True, True, False, False, False, False, True, True, False
    ]

    # Test the should_interrupt method logic
    test_should_interrupt_logic(vad, voice_activity_states)
