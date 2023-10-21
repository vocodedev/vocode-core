import os
from array import array
from typing import (
    Any,
    ClassVar,
    Iterator,
    Literal,
    NamedTuple,
    Sequence,
    TypedDict,
    BinaryIO,
    overload,
)

from typing_extensions import TypeAlias, Self

_PathLike: TypeAlias = str | bytes | os.PathLike[Any]
_AudioDataSource: TypeAlias = str | bytes | array[int] | BinaryIO

class _Metadata(TypedDict):
    channels: int
    frame_rate: int
    frame_width: int
    sample_width: int

class _PartialMetadata(TypedDict, total=False):
    channels: int
    frame_rate: int
    frame_width: int
    sample_width: int

class WavSubChunk(NamedTuple):
    id: bytes
    position: int
    size: int

class WavData(NamedTuple):
    audio_format: int
    channels: int
    sample_rate: int
    bits_per_sample: int
    raw_data: bytes

def extract_wav_headers(data: bytes) -> list[WavSubChunk]: ...  # undocumented
def read_wav_audio(data: bytes, headers: list[WavSubChunk] | None = ...) -> WavData: ...  # undocumented
def fix_wav_headers(data: bytes) -> None: ...  # undocumented

class AudioSegment:
    converter: ClassVar[str]
    DEFAULT_CODECS: ClassVar[dict[str, str]]
    @overload
    def __init__(self, data: _AudioDataSource) -> None: ...
    @overload
    def __init__(self, data: _AudioDataSource, *, sample_width: int, frame_rate: int, channels: int) -> None: ...
    @overload
    def __init__(self, data: _AudioDataSource, *, metadata: _Metadata) -> None: ...
    def __add__(self, arg: float | AudioSegment) -> AudioSegment: ...
    def __radd__(self, rarg: AudioSegment) -> AudioSegment: ...
    def __sub__(self, arg: float) -> AudioSegment: ...
    def __mul__(self, arg: int | AudioSegment) -> AudioSegment: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[AudioSegment]: ...
    def __getitem__(self, ms: int | slice) -> AudioSegment: ...
    def __getattr__(self, attr: str) -> Any: ...
    @property
    def channels(self) -> int: ...
    @property
    def sample_width(self) -> int: ...
    @property
    def frame_rate(self) -> int: ...
    @property
    def frame_width(self) -> int: ...
    @property
    def rms(self) -> float: ...
    @property
    def max(self) -> float: ...
    @property
    def dBFS(self) -> float: ...
    @property
    def max_dBFS(self) -> float: ...
    @property
    def max_possible_amplitude(self) -> float: ...
    @property
    def duration_seconds(self) -> int: ...
    @property
    def raw_data(self) -> bytes: ...
    @property
    def array_type(self) -> Literal["b", "B", "h", "H", "i", "I"]: ...
    def _spawn(
        self,
        data: _AudioDataSource | list[bytes],
        overrides: _PartialMetadata = ...,
    ) -> Self: ...
    def export(
        self,
        out_f: _PathLike | None = ...,
        *,
        format: str = ...,
        codec: str | None = ...,
        bitrate: str | None = ...,
        tags: dict[str, str] | None = ...,
        parameters: Sequence[str] | None = ...,
        id3v2_version: Literal["3", "4"] = ...,
        cover: str | None = ...,
    ) -> BinaryIO: ...
    def frame_count(self, ms: int = ...) -> float: ...
    def get_frame(self, index: int) -> bytes: ...
    def get_sample_slice(self, start_sample: int | None = ..., end_sample: int | None = ...) -> Self: ...
    def append(self, seg: AudioSegment, *, crossfade: int = ...) -> Self: ...
    def overlay(
        self,
        seg: AudioSegment,
        *,
        position: int = ...,
        loop: bool = ...,
        times: int | None = ...,
        gain_during_overlay: int | None = ...,
    ) -> Self: ...
    def apply_gain(self, volume_change: float) -> Self: ...
    @overload
    def fade(self, *, start: int, end: int, to_gain: float = ..., from_gain: float = ...) -> Self: ...
    @overload
    def fade(self, *, start: int, duration: int, to_gain: float = ..., from_gain: float = ...) -> Self: ...
    @overload
    def fade(self, *, end: int, duration: int, to_gain: float = ..., from_gain: float = ...) -> Self: ...
    def fade_out(self, duration: int) -> Self: ...
    def fade_in(self, duration: int) -> Self: ...
    def reverse(self) -> Self: ...
    def set_sample_width(self, sample_width: int) -> Self: ...
    def set_frame_rate(self, frame_rate: int) -> Self: ...
    def set_channels(self, channels: int) -> Self: ...
    def split_to_mono(self) -> list[Self]: ...
    def get_array_of_samples(
        self,
        array_type_override: Literal["b", "B", "h", "H", "i", "I", "l", "L", "q", "Q"] | None = ...,
    ) -> array[int]: ...
    def get_dc_offset(self, channel: Literal[1, 2]) -> int: ...
    def remove_dc_offset(self, channel: Literal[1, 2] | None = ..., offset: float | None = ...) -> Self: ...
    @overload
    @classmethod
    def from_file(
        cls,
        file: _PathLike,
        *,
        format: str | None = ...,
        codec: str | None = ...,
        read_ahead_limit: int = ...,
        parameters: Sequence[str] | None = ...,
        start_second: float | None = ...,
        duration: float | None = ...,
    ) -> Self: ...
    @overload
    @classmethod
    def from_file(
        cls,
        file: _PathLike,
        *,
        channels: int,
        frame_rate: int,
        sample_width: int,
        format: str | None = ...,
        codec: str | None = ...,
        read_ahead_limit: int = ...,
        parameters: Sequence[str] | None = ...,
        start_second: float | None = ...,
        duration: float | None = ...,
    ) -> Self: ...
    @overload
    @classmethod
    def from_file_using_temporary_files(
        cls,
        file: _PathLike,
        *,
        format: str | None = ...,
        codec: str | None = ...,
        parameters: Sequence[str] | None = ...,
        start_second: float | None = ...,
        duration: float | None = ...,
    ) -> Self: ...
    @overload
    @classmethod
    def from_file_using_temporary_files(
        cls,
        file: _PathLike,
        *,
        channels: int,
        frame_rate: int,
        sample_width: int,
        format: str | None = ...,
        codec: str | None = ...,
        parameters: Sequence[str] | None = ...,
        start_second: float | None = ...,
        duration: float | None = ...,
    ) -> Self: ...
    @classmethod
    def from_mp3(cls, file: _PathLike, parameters: Sequence[str] | None = ...) -> AudioSegment: ...
    @classmethod
    def from_flv(cls, file: _PathLike, parameters: Sequence[str] | None = ...) -> AudioSegment: ...
    @classmethod
    def from_ogg(cls, file: _PathLike, parameters: Sequence[str] | None = ...) -> AudioSegment: ...
    @classmethod
    def from_wav(cls, file: _PathLike, parameters: Sequence[str] | None = ...) -> AudioSegment: ...
    @classmethod
    def from_raw(cls, file: _PathLike, *, frame_rate: int, channels: int, sample_width: int) -> AudioSegment: ...
    @classmethod
    def empty(cls) -> Self: ...
    @classmethod
    def silent(cls, duration: int = ..., frame_rate: int = ...) -> Self: ...
    @classmethod
    def from_mono_audiosegments(cls, __seg: AudioSegment, /, *mono_segments: AudioSegment) -> Self: ...
