import ctypes
import re
from typing import Tuple

import numpy as np
from pydub import AudioSegment


def transcribe(whisper, params, ctx, audio_segment: AudioSegment) -> Tuple[str, float]:
    if len(audio_segment) <= 100:
        return "", 0.0
    normalized = (
        np.frombuffer(audio_segment.set_frame_rate(16000).raw_data, dtype=np.int16).astype(
            "float32"
        )
        / 32768.0
    )

    result = whisper.whisper_full(
        ctypes.c_void_p(ctx),
        params,
        normalized.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        len(normalized),
    )
    if result != 0:
        print("Error: {}".format(result))
        exit(1)
    text: str = whisper.whisper_full_get_segment_text(ctypes.c_void_p(ctx), 0).decode("utf-8")
    # heuristic to filter out non-speech
    if not re.search(r"^\w.*", text.strip()):
        return "", 0.0
    return text, 1.0
