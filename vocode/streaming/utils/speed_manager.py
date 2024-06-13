from loguru import logger

from vocode.streaming.models.transcriber import Transcription

LEARNING_RATE = 0.1
LENGTH_THRESHOLD = 5
SMOOTHING_FACTOR = 3
BASE_WPM = 150.0


class SpeedManager:
    """
    Uses the WPM of incoming transcriptions to update a speed coefficient to inform conversation orchestration.

    speed_coefficient is used in two places (currently):
    - DeepgramTranscriber endpointing - when we receive fast utterances from the user, we decrease the endpointing threshold to match the speed of the user
    - Interruption logic - if the user is speaking slowly, then when the agent is responding to an interrupt, we wait longer

    Initializes with a speed coefficient of 1.0, which corresponds to a WPM of 150.0 and uses a moving average to update the speed coefficient based on incoming transcriptions.
    """

    def __init__(self, speed_coefficient: float = 1.0):
        self.wpm_0 = BASE_WPM * speed_coefficient
        self.wpm = self.wpm_0
        self.speed_coefficient = speed_coefficient

    def update(self, transcription: Transcription):
        transcription_wpm = transcription.wpm()
        if transcription_wpm is not None:
            length = len(transcription.message.strip().split())
            p_t = min(
                1,
                LEARNING_RATE
                * ((length + SMOOTHING_FACTOR) / (LENGTH_THRESHOLD + SMOOTHING_FACTOR)),
            )
            self.wpm = self.wpm * (1 - p_t) + transcription_wpm * p_t
            self.speed_coefficient = self.wpm / BASE_WPM
            logger.info(f"Set speed coefficient to {self.speed_coefficient}")

    def get_speed_coefficient(self):
        return self.speed_coefficient

    def get_wpm(self):
        return self.wpm
