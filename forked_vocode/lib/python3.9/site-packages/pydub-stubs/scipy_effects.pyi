from typing import Literal, TypeVar, overload

from .audio_segment import AudioSegment

_AudioSegmentT = TypeVar("_AudioSegmentT", bound=AudioSegment)

# The first overload is the only one using the _eq method (if `channel_mode` == "L+R")
# and _eq will return the same instance of seg, so we need to use the TypeVar in this case.
@overload
def eq(
    seg: _AudioSegmentT,
    focus_freq: int,
    bandwidth: int = ...,
    channel_mode: Literal["L+R"] = ...,
    filter_mode: Literal["peak", "low_shelf", "high_shelf"] = ...,
    gain_dB: int = ...,
    order: int = ...,
) -> _AudioSegmentT: ...
@overload
def eq(
    seg: AudioSegment,
    focus_freq: int,
    bandwidth: int = ...,
    channel_mode: Literal["L", "R", "M+S", "M", "S"] = ...,
    filter_mode: Literal["peak", "low_shelf", "high_shelf"] = ...,
    gain_dB: int = ...,
    order: int = ...,
) -> AudioSegment: ...
def low_pass_filter(seg: _AudioSegmentT, cutoff_freq: float, order: int = ...) -> _AudioSegmentT: ...
def high_pass_filter(seg: _AudioSegmentT, cutoff_freq: float, order: int = ...) -> _AudioSegmentT: ...
def band_pass_filter(
    seg: _AudioSegmentT, low_cutoff_freq: float, high_cutoff_freq: float, order: int = ...
) -> _AudioSegmentT: ...
