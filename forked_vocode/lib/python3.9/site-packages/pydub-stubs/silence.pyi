from typing import TypeVar

from .audio_segment import AudioSegment

_AudioSegmentT = TypeVar("_AudioSegmentT", bound=AudioSegment)

def detect_silence(
    audio_segment: AudioSegment, *, min_silence_len: int = ..., silence_thresh: float = ..., seek_step: int = ...
) -> list[list[int]]: ...
def detect_nonsilent(
    audio_segment: AudioSegment, *, min_silence_len: int = ..., silence_thresh: float = ..., seek_step: int = ...
) -> list[list[int]]: ...
def split_on_silence(
    audio_segment: _AudioSegmentT,
    *,
    min_silence_len: int = ...,
    silence_thresh: float = ...,
    keep_silence: float | bool = ...,
    seek_step: int = ...,
) -> list[_AudioSegmentT]: ...
def detect_leading_silence(sound: AudioSegment, *, silence_threshold: float = ..., chunk_size: int = ...) -> int: ...
