import audioop
import io
import wave

import miniaudio
from pydub import AudioSegment


# sampling_rate is the rate of the input, not expected output
def decode_mp3(mp3_bytes: bytes) -> io.BytesIO:
    # Convert it to a wav chunk using miniaudio
    wav_chunk = miniaudio.decode(mp3_bytes, nchannels=1)

    # Write wav_chunks.samples to io.BytesIO with builtin WAVE
    output_bytes_io = io.BytesIO()

    with wave.open(output_bytes_io, "wb") as wave_obj:
        wave_obj.setnchannels(1)
        wave_obj.setsampwidth(2)
        wave_obj.setframerate(44100)
        wave_obj.writeframes(wav_chunk.samples)
    output_bytes_io.seek(0)
    return output_bytes_io

def ulaw_pcm_to_mp3(pcm_data, sample_rate=8000, sample_width=2, channels=1, bitrate="64k"):
    pcm_lin_data = audioop.ulaw2lin(pcm_data, sample_width)

    audio = AudioSegment(
        data=pcm_lin_data,
        sample_width=sample_width,
        frame_rate=sample_rate,
        channels=channels)

    mp3_buffer = io.BytesIO()
    audio.export(mp3_buffer, format="mp3", bitrate=bitrate)
    return mp3_buffer.getvalue()

