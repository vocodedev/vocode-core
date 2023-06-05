from vocode.streaming.models.audio_encoding import AudioEncoding

# TODO(EPD-186): namespace as Twilio
DEFAULT_SAMPLING_RATE = 8000
DEFAULT_AUDIO_ENCODING = AudioEncoding.MULAW
DEFAULT_CHUNK_SIZE = 20 * 160

VONAGE_SAMPLING_RATE = 16000
VONAGE_AUDIO_ENCODING = AudioEncoding.LINEAR16
VONAGE_CHUNK_SIZE = 640  # 20ms at 16kHz with 16bit samples
VONAGE_CONTENT_TYPE = "audio/l16;rate=16000"
