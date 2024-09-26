import asyncio
import audioop
import logging
import os
import secrets
from typing import Any
import wave
from string import ascii_letters, digits

from ..models.audio_encoding import AudioEncoding

logger = logging.getLogger(__name__)
custom_alphabet = ascii_letters + digits + ".-_"

AZURE_PHONETIC_SYMBOLS = {
    0: "silence",
    1: "æ, ə, ʌ",
    2: "ɑ",
    3: "ɔ",
    4: "ɛ, ʊ",
    5: "ɝ",
    6: "j, i, ɪ",
    7: "w, u",
    8: "o",
    9: "aʊ",
    10: "ɔɪ",
    11: "aɪ",
    12: "h",
    13: "ɹ",
    14: "l",
    15: "s, z",
    16: "ʃ, tʃ, dʒ, ʒ",
    17: "ð",
    18: "f, v",
    19: "d, t, n, θ",
    20: "k, g, ŋ",
    21: "p, b, m",
}

AZURE_TO_OVR = {
  0: "viseme_sil",
  1: "viseme_aa",
  2: "viseme_aa",
  3: "viseme_aa",
  4: "viseme_U",
  5: "viseme_nn",
  6: "viseme_I",
  7: "viseme_O",
  8: "viseme_O",
  9: "viseme_aa",
  10: "viseme_O",
  11: "viseme_aa",
  12: "viseme_U",
  13: "viseme_RR",
  14: "viseme_nn",
  15: "viseme_SS",
  16: "viseme_CH",
  17: "viseme_TH",
  18: "viseme_FF",
  19: "viseme_DD",
  20: "viseme_kk",
  21: "viseme_PP",
}

def create_loop_in_thread(loop: asyncio.AbstractEventLoop, long_running_task=None):
    asyncio.set_event_loop(loop)
    if long_running_task:
        loop.run_until_complete(long_running_task)
    else:
        loop.run_forever()


def convert_linear_audio(
    raw_wav: bytes,
    input_sample_rate=24000,
    output_sample_rate=8000,
    output_encoding=AudioEncoding.LINEAR16,
    output_sample_width=2,
):
    # downsample
    if input_sample_rate != output_sample_rate:
        raw_wav, _ = audioop.ratecv(
            raw_wav, 2, 1, input_sample_rate, output_sample_rate, None
        )

    if output_encoding == AudioEncoding.LINEAR16:
        return raw_wav
    elif output_encoding == AudioEncoding.MULAW:
        return audioop.lin2ulaw(raw_wav, output_sample_width)


def convert_wav(
    file: Any,
    output_sample_rate=8000,
    output_encoding=AudioEncoding.LINEAR16,
):
    with wave.open(file, "rb") as wav:
        raw_wav = wav.readframes(wav.getnframes())
        return convert_linear_audio(
            raw_wav,
            input_sample_rate=wav.getframerate(),
            output_sample_rate=output_sample_rate,
            output_encoding=output_encoding,
            output_sample_width=wav.getsampwidth(),
        )


def get_chunk_size_per_second(audio_encoding: AudioEncoding, sampling_rate: int) -> int:
    if audio_encoding == AudioEncoding.LINEAR16:
        return sampling_rate * 2
    elif audio_encoding == AudioEncoding.MULAW:
        return sampling_rate
    else:
        raise Exception("Unsupported audio encoding")


def create_conversation_id() -> str:
    return secrets.token_urlsafe(16)

def remove_non_letters_digits(text):
    return ''.join(i for i in text if i in custom_alphabet)

def print_visemes(lipsync_events, lookup_table):
    out = ""
    for event in lipsync_events:
        out += f'{event["audio_offset"]}\t{event["audio_offset"]}\t{lookup_table[event["viseme_id"]]}\n'
    return out

def save_as_wav(path, audio_data: bytes, sampling_rate: int):
    if len(audio_data) == 0:
        logger.error(f"Cannot save an empty WAV file to {path}")
        return
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        wav_file = wave.open(f, "wb")
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sampling_rate)
        wav_file.writeframes(audio_data)
        wav_file.close()
    logger.debug(f"Saved {len(audio_data)} audio bytes to {path}")

def trim_audio(
        sampling_rate: int,
        audio_buffer: bytearray,
        total_bytes: int,
        offset_s: float,
        duration_s: float,
    ):
    """
    Extracts / trims an audio buffer to match the given offset and duration.

    Args:
        sampling_rate: sampling rate of audio buffer
        audio_buffer: The audio buffer. May have been truncated, e.g. length may be < total_bytes
        total_bytes: The total number of bytes recorded since starting the stream
        offset_s: The offset in seconds since start of stream, to start trimming from
        duration_s: The duration in seconds to trim
    """
    bytes_per_sample = 2

    offset_bytes = int(max(0, offset_s) * bytes_per_sample * sampling_rate)
    duration_bytes = int(max(0, duration_s) * bytes_per_sample * sampling_rate)

    # Because audio_buffer only represents last x seconds (bytes may have been discarded since stream started), 
    # we need to shift the offset bytes to fit inside it
    if offset_bytes + duration_bytes > total_bytes:
            duration_bytes = total_bytes - offset_bytes
    # We may have discarded earlier audio so we need to adjust the offset
    offset_bytes -= total_bytes
    offset_bytes += len(audio_buffer)
    offset_bytes = max(0, offset_bytes)
    if duration_bytes == 0 or len(audio_buffer) <= (bytes_per_sample * sampling_rate):
        trimmed_audio = audio_buffer
    else:
        trimmed_audio = audio_buffer[offset_bytes : offset_bytes + duration_bytes]
    return trimmed_audio