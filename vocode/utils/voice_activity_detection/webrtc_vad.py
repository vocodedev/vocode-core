from vocode.utils.voice_activity_detection.vad import BaseVoiceActivityDetector, BaseVoiceActivityDetectorConfig


class WebRTCVoiceActivityDetectorConfig(BaseVoiceActivityDetectorConfig):
    pass


class WebRTCVoiceActivityDetector(BaseVoiceActivityDetector[WebRTCVoiceActivityDetectorConfig]):
    def __init__(self, config: WebRTCVoiceActivityDetectorConfig):
        import webrtcvad
        super().__init__(config)
        self.vad = webrtcvad.Vad()

    def is_voice_active(self, frame: str) -> bool:
        return self.vad.is_speech(frame, self.config.frame_rate)
