import io
import wave
import miniaudio


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
