from vocode.streaming.models.audio import AudioEncoding, SamplingRate

# TODO(EPD-186): namespace as Twilio
DEFAULT_SAMPLING_RATE = SamplingRate.RATE_8000
DEFAULT_AUDIO_ENCODING = AudioEncoding.MULAW
DEFAULT_CHUNK_SIZE = 20 * 160
MULAW_SILENCE_BYTE = b"\xff"

VONAGE_SAMPLING_RATE = SamplingRate.RATE_16000
VONAGE_AUDIO_ENCODING = AudioEncoding.LINEAR16
VONAGE_CHUNK_SIZE = 640  # 20ms at 16kHz with 16bit samples
VONAGE_CONTENT_TYPE = "audio/l16;rate=16000"
PCM_SILENCE_BYTE = b"\x00"
