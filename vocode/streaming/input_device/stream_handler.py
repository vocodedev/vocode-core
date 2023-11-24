from vocode.streaming.input_device.rnn_noise import RNNoiseWrapper
from vocode.streaming.transcriber import BaseTranscriber


class StreamHandler:
    # ... other methods ...

    def __init__(self, transcriber: BaseTranscriber):
        self.transcriber = transcriber
        if transcriber.transcriber_config.denoise:
            self.rnnoise_wrapper = RNNoiseWrapper()
        else:
            self.rnnoise_wrapper = None

    def receive_audio(self, chunk: bytes):
        if self.rnnoise_wrapper:
            chunk, vad_prob = self.rnnoise_wrapper.process_frame(chunk)

        self.transcriber.send_audio(chunk)
