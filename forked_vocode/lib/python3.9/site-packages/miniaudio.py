"""
Python interface to the miniaudio library (https://github.com/dr-soft/miniaudio)

Author: Irmen de Jong (irmen@razorvine.net)
Software license: "MIT software license". See http://opensource.org/licenses/MIT
"""

__version__ = "1.59"


import abc
import sys
import os
import io
import array
import urllib.request
import inspect
import time
import threading
from enum import Enum
from typing import Generator, List, Dict, Set, Optional, Union, Any, Callable
from _miniaudio import ffi, lib
try:
    import numpy
except ImportError:
    numpy = None        # type: ignore

lib.init_miniaudio()


class FileFormat(Enum):
    """Audio file format"""
    UNKNOWN = lib.ma_encoding_format_unknown
    WAV = lib.ma_encoding_format_wav
    FLAC = lib.ma_encoding_format_flac
    MP3 = lib.ma_encoding_format_mp3
    VORBIS = lib.ma_encoding_format_vorbis


class SampleFormat(Enum):
    """Sample format in memory"""
    UNKNOWN = lib.ma_format_unknown
    UNSIGNED8 = lib.ma_format_u8
    SIGNED16 = lib.ma_format_s16
    SIGNED24 = lib.ma_format_s24
    SIGNED32 = lib.ma_format_s32
    FLOAT32 = lib.ma_format_f32


class DeviceType(Enum):
    """Type of audio device"""
    PLAYBACK = lib.ma_device_type_playback
    CAPTURE = lib.ma_device_type_capture
    DUPLEX = lib.ma_device_type_duplex


class DitherMode(Enum):
    """How to dither when converting"""
    NONE = lib.ma_dither_mode_none
    RECTANGLE = lib.ma_dither_mode_rectangle
    TRIANGLE = lib.ma_dither_mode_triangle


class ChannelMixMode(Enum):
    """How to mix channels when converting"""
    RECTANGULAR = lib.ma_channel_mix_mode_rectangular
    SIMPLE = lib.ma_channel_mix_mode_simple
    CUSTOMWEIGHTS = lib.ma_channel_mix_mode_custom_weights
    DEFAULT = lib.ma_channel_mix_mode_default


class Backend(Enum):
    """Operating system audio backend to use (only a subset will be available)"""
    WASAPI = lib.ma_backend_wasapi
    DSOUND = lib.ma_backend_dsound
    WINMM = lib.ma_backend_winmm
    COREAUDIO = lib.ma_backend_coreaudio
    SNDIO = lib.ma_backend_sndio
    AUDIO4 = lib.ma_backend_audio4
    OSS = lib.ma_backend_oss
    PULSEAUDIO = lib.ma_backend_pulseaudio
    ALSA = lib.ma_backend_alsa
    JACK = lib.ma_backend_jack
    AAUDIO = lib.ma_backend_aaudio
    OPENSL = lib.ma_backend_opensl
    WEBAUDIO = lib.ma_backend_webaudio
    CUSTOM = lib.ma_backend_custom
    NULL = lib.ma_backend_null


class ThreadPriority(Enum):
    """The priority of the worker thread (default=HIGHEST)"""
    IDLE = lib.ma_thread_priority_idle
    LOWEST = lib.ma_thread_priority_lowest
    LOW = lib.ma_thread_priority_low
    NORMAL = lib.ma_thread_priority_normal
    HIGH = lib.ma_thread_priority_high
    HIGHEST = lib.ma_thread_priority_highest
    REALTIME = lib.ma_thread_priority_realtime
    DEFAULT = lib.ma_thread_priority_default


class SeekOrigin(Enum):
    """How to seek() in a source"""
    START = lib.ma_seek_origin_start
    CURRENT = lib.ma_seek_origin_current


FramesType = Union[bytes, array.array]
PlaybackCallbackGeneratorType = Generator[FramesType, int, None]
CaptureCallbackGeneratorType = Generator[None, FramesType, None]
DuplexCallbackGeneratorType = Generator[FramesType, FramesType, None]
GeneratorTypes = Union[PlaybackCallbackGeneratorType, CaptureCallbackGeneratorType, DuplexCallbackGeneratorType]


class SoundFileInfo:
    """Contains various properties of an audio file."""
    def __init__(self, name: str, file_format: FileFormat, nchannels: int, sample_rate: int,
                 sample_format: SampleFormat, duration: float, num_frames: int,
                 sub_format: int = None) -> None:
        self.name = name
        self.nchannels = nchannels
        self.sample_rate = sample_rate
        self.sample_format = sample_format
        self.sample_format_name = ffi.string(lib.ma_get_format_name(sample_format.value)).decode()
        self.sample_width = width_from_format(sample_format)
        self.num_frames = num_frames
        self.duration = duration
        self.file_format = file_format
        self.sub_format = sub_format

    def __str__(self) -> str:
        fileformatdisplay = self.file_format.name
        if self.sub_format:
            fileformatdisplay += " (fmt=" + str(self.sub_format) + ")"
        return "<{clazz}: '{name}' {fileformatdisplay} {nchannels} ch, {sample_rate} hz, {sample_format.name}, " \
               "{num_frames} frames={duration:.2f} sec.>".format(clazz=self.__class__.__name__,
                                                                 fileformatdisplay=fileformatdisplay, **(vars(self)))

    def __repr__(self) -> str:
        return str(self)


class DecodedSoundFile(SoundFileInfo):
    """Contains various properties and also the PCM frames of a fully decoded audio file."""
    def __init__(self, name: str, nchannels: int, sample_rate: int,
                 sample_format: SampleFormat, samples: array.array) -> None:
        num_frames = len(samples) // nchannels
        duration = num_frames / sample_rate
        super().__init__(name, FileFormat.UNKNOWN, nchannels, sample_rate, sample_format, duration, num_frames)
        self.samples = samples


class MiniaudioError(Exception):
    """When a miniaudio specific error occurs."""
    pass


class DecodeError(MiniaudioError):
    """When something went wrong during decoding an audio file."""
    pass


def get_file_info(filename: str) -> SoundFileInfo:
    """Fetch some information about the audio file."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".ogg", ".vorbis"):
        return vorbis_get_file_info(filename)
    elif ext == ".mp3":
        return mp3_get_file_info(filename)
    elif ext == ".flac":
        return flac_get_file_info(filename)
    elif ext == ".wav":
        return wav_get_file_info(filename)
    raise DecodeError("unsupported file format")


def read_file(filename: str, convert_to_16bit: bool = False) -> DecodedSoundFile:
    """Reads and decodes the whole audio file.
    Miniaudio will attempt to return the sound data in exactly the same format as in the file.
    Unless you set convert_convert_to_16bit to True, then the result is always a 16 bit sample format.
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".ogg", ".vorbis"):
        if convert_to_16bit:
            return vorbis_read_file(filename)
        else:
            vorbis = vorbis_get_file_info(filename)
            if vorbis.sample_format == SampleFormat.SIGNED16:
                return vorbis_read_file(filename)
            else:
                raise MiniaudioError("file has sample format that must be converted")
    elif ext == ".mp3":
        if convert_to_16bit:
            return mp3_read_file_s16(filename)
        else:
            mp3 = mp3_get_file_info(filename)
            if mp3.sample_format == SampleFormat.SIGNED16:
                return mp3_read_file_s16(filename)
            elif mp3.sample_format == SampleFormat.FLOAT32:
                return mp3_read_file_f32(filename)
            else:
                raise MiniaudioError("file has sample format that must be converted")
    elif ext == ".flac":
        if convert_to_16bit:
            return flac_read_file_s16(filename)
        else:
            flac = flac_get_file_info(filename)
            if flac.sample_format == SampleFormat.SIGNED16:
                return flac_read_file_s16(filename)
            elif flac.sample_format == SampleFormat.SIGNED32:
                return flac_read_file_s32(filename)
            elif flac.sample_format == SampleFormat.FLOAT32:
                return flac_read_file_f32(filename)
            else:
                raise MiniaudioError("file has sample format that must be converted")
    elif ext == ".wav":
        if convert_to_16bit:
            return wav_read_file_s16(filename)
        else:
            wav = wav_get_file_info(filename)
            if wav.sample_format == SampleFormat.SIGNED16:
                return wav_read_file_s16(filename)
            elif wav.sample_format == SampleFormat.SIGNED32:
                return wav_read_file_s32(filename)
            elif wav.sample_format == SampleFormat.FLOAT32:
                return wav_read_file_f32(filename)
            else:
                raise MiniaudioError("file has sample format that must be converted")
    raise DecodeError("unsupported file format")


def vorbis_get_file_info(filename: str) -> SoundFileInfo:
    """Fetch some information about the audio file (vorbis format)."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("int *") as error:
        vorbis = lib.stb_vorbis_open_filename(filenamebytes, error, ffi.NULL)
        if not vorbis:
            raise DecodeError("could not open/decode file")
        try:
            info = lib.stb_vorbis_get_info(vorbis)
            duration = lib.stb_vorbis_stream_length_in_seconds(vorbis)
            num_frames = lib.stb_vorbis_stream_length_in_samples(vorbis)
            return SoundFileInfo(filename, FileFormat.VORBIS, info.channels, info.sample_rate,
                                 SampleFormat.SIGNED16, duration, num_frames)
        finally:
            lib.stb_vorbis_close(vorbis)


def vorbis_get_info(data: bytes) -> SoundFileInfo:
    """Fetch some information about the audio data (vorbis format)."""
    with ffi.new("int *") as error:
        vorbis = lib.stb_vorbis_open_memory(data, len(data), error, ffi.NULL)
        if not vorbis:
            raise DecodeError("could not open/decode data")
        try:
            info = lib.stb_vorbis_get_info(vorbis)
            duration = lib.stb_vorbis_stream_length_in_seconds(vorbis)
            num_frames = lib.stb_vorbis_stream_length_in_samples(vorbis)
            return SoundFileInfo("<memory>", FileFormat.VORBIS, info.channels, info.sample_rate,
                                 SampleFormat.SIGNED16, duration, num_frames)
        finally:
            lib.stb_vorbis_close(vorbis)


def vorbis_read_file(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole vorbis audio file. Resulting sample format is 16 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("int *") as channels, ffi.new("int *") as sample_rate, ffi.new("short **") as output:
        num_frames = lib.stb_vorbis_decode_filename(filenamebytes, channels, sample_rate, output)
        if num_frames <= 0:
            raise DecodeError("cannot load/decode file")
        try:
            buffer = ffi.buffer(output[0], num_frames * channels[0] * 2)
            samples = _create_int_array(2)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.free(output[0])


def vorbis_read(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole vorbis audio data. Resulting sample format is 16 bits signed integer."""
    with ffi.new("int *") as channels, ffi.new("int *") as sample_rate, ffi.new("short **") as output:
        num_samples = lib.stb_vorbis_decode_memory(data, len(data), channels, sample_rate, output)
        if num_samples <= 0:
            raise DecodeError("cannot load/decode data")
        try:
            buffer = ffi.buffer(output[0], num_samples * channels[0] * 2)
            samples = _create_int_array(2)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.free(output[0])


def vorbis_stream_file(filename: str, seek_frame: int = 0) -> Generator[array.array, None, None]:
    """Streams the ogg vorbis audio file as interleaved 16 bit signed integer sample arrays segments.
    This uses a variable unconfigurable chunk size and cannot be used as a generic miniaudio decoder input stream.
    Consider using stream_file() instead."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("int *") as error:
        vorbis = lib.stb_vorbis_open_filename(filenamebytes, error, ffi.NULL)
        if not vorbis:
            raise DecodeError("could not open/decode file")
        try:
            info = lib.stb_vorbis_get_info(vorbis)
            with ffi.new("short[]", 4096 * info.channels) as decode_buffer1, \
                ffi.new("short[]", 4096 * info.channels) as decode_buffer2:
                decodebuf_ptr1 = ffi.cast("short *", decode_buffer1)
                decodebuf_ptr2 = ffi.cast("short *", decode_buffer2)
                if seek_frame > 0:
                    result = lib.stb_vorbis_seek_frame(vorbis, seek_frame)
                    if result <= 0:
                        raise DecodeError("can't seek")
                # note: we decode several frames to reduce the overhead of very small sample sizes a little
                while True:
                    num_samples1 = lib.stb_vorbis_get_frame_short_interleaved(vorbis, info.channels, decodebuf_ptr1,
                                                                              4096 * info.channels)
                    num_samples2 = lib.stb_vorbis_get_frame_short_interleaved(vorbis, info.channels, decodebuf_ptr2,
                                                                              4096 * info.channels)
                    if num_samples1 + num_samples2 <= 0:
                        break
                    buffer = ffi.buffer(decode_buffer1, num_samples1 * 2 * info.channels)
                    samples = _create_int_array(2)
                    samples.frombytes(buffer)
                    if num_samples2 > 0:
                        buffer = ffi.buffer(decode_buffer2, num_samples2 * 2 * info.channels)
                        samples.frombytes(buffer)
                    yield samples
        finally:
            lib.stb_vorbis_close(vorbis)


def flac_get_file_info(filename: str) -> SoundFileInfo:
    """Fetch some information about the audio file (flac format)."""
    filenamebytes = _get_filename_bytes(filename)
    flac = lib.drflac_open_file(filenamebytes, ffi.NULL)
    if not flac:
        raise DecodeError("could not open/decode file")
    try:
        duration = flac.totalPCMFrameCount / flac.sampleRate
        sample_width = flac.bitsPerSample // 8
        return SoundFileInfo(filename, FileFormat.FLAC, flac.channels, flac.sampleRate,
                             _format_from_width(sample_width), duration, flac.totalPCMFrameCount)
    finally:
        lib.drflac_close(flac)


def flac_get_info(data: bytes) -> SoundFileInfo:
    """Fetch some information about the audio data (flac format)."""
    flac = lib.drflac_open_memory(data, len(data), ffi.NULL)
    if not flac:
        raise DecodeError("could not open/decode data")
    try:
        duration = flac.totalPCMFrameCount / flac.sampleRate
        sample_width = flac.bitsPerSample // 8
        return SoundFileInfo("<memory>", FileFormat.FLAC, flac.channels, flac.sampleRate,
                             _format_from_width(sample_width), duration, flac.totalPCMFrameCount)
    finally:
        lib.drflac_close(flac)


def flac_read_file_s32(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio file. Resulting sample format is 32 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_file_and_read_pcm_frames_s32(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = _create_int_array(4)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.SIGNED32, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_read_file_s16(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio file. Resulting sample format is 16 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_file_and_read_pcm_frames_s16(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_read_file_f32(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio file. Resulting sample format is 32 bits float."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_file_and_read_pcm_frames_f32(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.FLOAT32, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_read_s32(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio data. Resulting sample format is 32 bits signed integer."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_memory_and_read_pcm_frames_s32(data, len(data),
                                                                channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = _create_int_array(4)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.SIGNED32, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_read_s16(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio data. Resulting sample format is 16 bits signed integer."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_memory_and_read_pcm_frames_s16(data, len(data),
                                                                channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_read_f32(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole flac audio file. Resulting sample format is 32 bits float."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drflac_uint64 *") as num_frames:
        memory = lib.drflac_open_memory_and_read_pcm_frames_f32(data, len(data),
                                                                channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.FLOAT32, samples)
        finally:
            lib.drflac_free(memory, ffi.NULL)


def flac_stream_file(filename: str, frames_to_read: int = 1024,
                     seek_frame: int = 0) -> Generator[array.array, None, None]:
    """Streams the flac audio file as interleaved 16 bit signed integer sample arrays segments.
    This uses a fixed chunk size and cannot be used as a generic miniaudio decoder input stream.
    Consider using stream_file() instead."""
    filenamebytes = _get_filename_bytes(filename)
    flac = lib.drflac_open_file(filenamebytes, ffi.NULL)
    if not flac:
        raise DecodeError("could not open/decode file")
    if seek_frame > 0:
        result = lib.drflac_seek_to_pcm_frame(flac, seek_frame)
        if result <= 0:
            raise DecodeError("can't seek")
    try:
        with ffi.new("drflac_int16[]", frames_to_read * flac.channels) as decodebuffer:
            buf_ptr = ffi.cast("drflac_int16 *", decodebuffer)
            while True:
                num_samples = lib.drflac_read_pcm_frames_s16(flac, frames_to_read, buf_ptr)
                if num_samples <= 0:
                    break
                buffer = ffi.buffer(decodebuffer, num_samples * 2 * flac.channels)
                samples = _create_int_array(2)
                samples.frombytes(buffer)
                yield samples
    finally:
        lib.drflac_close(flac)


def mp3_get_file_info(filename: str) -> SoundFileInfo:
    """Fetch some information about the audio file (mp3 format)."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drmp3 *") as mp3:
        if not lib.drmp3_init_file(mp3, filenamebytes, ffi.NULL):
            raise DecodeError("could not open/decode file")
        try:
            num_frames = lib.drmp3_get_pcm_frame_count(mp3)
            duration = num_frames / mp3.sampleRate
            return SoundFileInfo(filename, FileFormat.MP3, mp3.channels, mp3.sampleRate,
                                 SampleFormat.SIGNED16, duration, num_frames)
        finally:
            lib.drmp3_uninit(mp3)


def mp3_get_info(data: bytes) -> SoundFileInfo:
    """Fetch some information about the audio data (mp3 format)."""
    with ffi.new("drmp3 *") as mp3:
        if not lib.drmp3_init_memory(mp3, data, len(data), ffi.NULL):
            raise DecodeError("could not open/decode data")
        try:
            num_frames = lib.drmp3_get_pcm_frame_count(mp3)
            duration = num_frames / mp3.sampleRate
            return SoundFileInfo("<memory>", FileFormat.MP3, mp3.channels, mp3.sampleRate,
                                 SampleFormat.SIGNED16, duration, num_frames)
        finally:
            lib.drmp3_uninit(mp3)


def mp3_read_file_f32(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole mp3 audio file. Resulting sample format is 32 bits float."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drmp3_config *") as config, ffi.new("drmp3_uint64 *") as num_frames:
        memory = lib.drmp3_open_file_and_read_pcm_frames_f32(filenamebytes, config, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * config.channels * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, config.channels, config.sampleRate, SampleFormat.FLOAT32, samples)
        finally:
            lib.drmp3_free(memory, ffi.NULL)


def mp3_read_file_s16(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole mp3 audio file. Resulting sample format is 16 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drmp3_config *") as config, ffi.new("drmp3_uint64 *") as num_frames:
        memory = lib.drmp3_open_file_and_read_pcm_frames_s16(filenamebytes, config, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * config.channels * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, config.channels, config.sampleRate, SampleFormat.SIGNED16, samples)
        finally:
            lib.drmp3_free(memory, ffi.NULL)


def mp3_read_f32(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole mp3 audio data. Resulting sample format is 32 bits float."""
    with ffi.new("drmp3_config *") as config, ffi.new("drmp3_uint64 *") as num_frames:
        memory = lib.drmp3_open_memory_and_read_pcm_frames_f32(data, len(data), config, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * config.channels * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", config.channels, config.sampleRate, SampleFormat.FLOAT32, samples)
        finally:
            lib.drmp3_free(memory, ffi.NULL)


def mp3_read_s16(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole mp3 audio data. Resulting sample format is 16 bits signed integer."""
    with ffi.new("drmp3_config *") as config, ffi.new("drmp3_uint64 *") as num_frames:
        memory = lib.drmp3_open_memory_and_read_pcm_frames_s16(data, len(data), config, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * config.channels * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", config.channels, config.sampleRate, SampleFormat.SIGNED16, samples)
        finally:
            lib.drmp3_free(memory, ffi.NULL)


def mp3_stream_file(filename: str, frames_to_read: int = 1024, seek_frame: int = 0) -> Generator[array.array, None, None]:
    """Streams the mp3 audio file as interleaved 16 bit signed integer sample arrays segments.
    This uses a fixed chunk size and cannot be used as a generic miniaudio decoder input stream.
    Consider using stream_file() instead."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drmp3 *") as mp3:
        if not lib.drmp3_init_file(mp3, filenamebytes, ffi.NULL):
            raise DecodeError("could not open/decode file")
        if seek_frame > 0:
            result = lib.drmp3_seek_to_pcm_frame(mp3, seek_frame)
            if result <= 0:
                raise DecodeError("can't seek")
        try:
            with ffi.new("drmp3_int16[]", frames_to_read * mp3.channels) as decodebuffer:
                buf_ptr = ffi.cast("drmp3_int16 *", decodebuffer)
                while True:
                    num_samples = lib.drmp3_read_pcm_frames_s16(mp3, frames_to_read, buf_ptr)
                    if num_samples <= 0:
                        break
                    buffer = ffi.buffer(decodebuffer, num_samples * 2 * mp3.channels)
                    samples = _create_int_array(2)
                    samples.frombytes(buffer)
                    yield samples
        finally:
            lib.drmp3_uninit(mp3)


def wav_get_file_info(filename: str) -> SoundFileInfo:
    """Fetch some information about the audio file (wav format)."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drwav*") as wav:
        if not lib.drwav_init_file(wav, filenamebytes, ffi.NULL):
            raise DecodeError("could not open/decode file")
        try:
            duration = wav.totalPCMFrameCount / wav.sampleRate
            sample_width = wav.bitsPerSample // 8
            is_float = wav.translatedFormatTag == lib.DR_WAVE_FORMAT_IEEE_FLOAT
            subformat = wav.translatedFormatTag
            return SoundFileInfo(filename, FileFormat.WAV, wav.channels, wav.sampleRate,
                                 _format_from_width(sample_width, is_float), duration, wav.totalPCMFrameCount,
                                 sub_format=subformat)
        finally:
            lib.drwav_uninit(wav)


def wav_get_info(data: bytes) -> SoundFileInfo:
    """Fetch some information about the audio data (wav format)."""
    with ffi.new("drwav*") as wav:
        if not lib.drwav_init_memory(wav, data, len(data), ffi.NULL):
            raise DecodeError("could not open/decode data")
        try:
            duration = wav.totalPCMFrameCount / wav.sampleRate
            sample_width = wav.bitsPerSample // 8
            is_float = wav.translatedFormatTag == lib.DR_WAVE_FORMAT_IEEE_FLOAT
            return SoundFileInfo("<memory>", FileFormat.WAV, wav.channels, wav.sampleRate,
                                 _format_from_width(sample_width, is_float), duration, wav.totalPCMFrameCount)
        finally:
            lib.drwav_uninit(wav)


def wav_read_file_s32(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio file. Resulting sample format is 32 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_file_and_read_pcm_frames_s32(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = _create_int_array(4)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.SIGNED32, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_read_file_s16(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio file. Resulting sample format is 16 bits signed integer."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_file_and_read_pcm_frames_s16(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_read_file_f32(filename: str) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio file. Resulting sample format is 32 bits float."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_file_and_read_pcm_frames_f32(filenamebytes, channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode file")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile(filename, channels[0], sample_rate[0], SampleFormat.FLOAT32, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_read_s32(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio data. Resulting sample format is 32 bits signed integer."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_memory_and_read_pcm_frames_s32(data, len(data), channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = _create_int_array(4)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.SIGNED32, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_read_s16(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio data. Resulting sample format is 16 bits signed integer."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_memory_and_read_pcm_frames_s16(data, len(data), channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = _create_int_array(2)
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 2)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.SIGNED16, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_read_f32(data: bytes) -> DecodedSoundFile:
    """Reads and decodes the whole wav audio data. Resulting sample format is 32 bits float."""
    with ffi.new("unsigned int *") as channels, \
        ffi.new("unsigned int *") as sample_rate, \
        ffi.new("drwav_uint64 *") as num_frames:
        memory = lib.drwav_open_memory_and_read_pcm_frames_f32(data, len(data), channels, sample_rate, num_frames, ffi.NULL)
        if not memory:
            raise DecodeError("cannot load/decode data")
        try:
            samples = array.array('f')
            buffer = ffi.buffer(memory, num_frames[0] * channels[0] * 4)
            samples.frombytes(buffer)
            return DecodedSoundFile("<memory>", channels[0], sample_rate[0], SampleFormat.FLOAT32, samples)
        finally:
            lib.drwav_free(memory, ffi.NULL)


def wav_stream_file(filename: str, frames_to_read: int = 1024,
                    seek_frame: int = 0) -> Generator[array.array, None, None]:
    """Streams the WAV audio file as interleaved 16 bit signed integer sample arrays segments.
    This uses a fixed chunk size and cannot be used as a generic miniaudio decoder input stream.
    Consider using stream_file() instead."""
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("drwav*") as wav:
        if not lib.drwav_init_file(wav, filenamebytes, ffi.NULL):
            raise DecodeError("could not open/decode file")
        if seek_frame > 0:
            result = lib.drwav_seek_to_pcm_frame(wav, seek_frame)
            if result <= 0:
                raise DecodeError("can't seek")
        try:
            with ffi.new("drwav_int16[]", frames_to_read * wav.channels) as decodebuffer:
                buf_ptr = ffi.cast("drwav_int16 *", decodebuffer)
                while True:
                    num_samples = lib.drwav_read_pcm_frames_s16(wav, frames_to_read, buf_ptr)
                    if num_samples <= 0:
                        break
                    buffer = ffi.buffer(decodebuffer, num_samples * 2 * wav.channels)
                    samples = _create_int_array(2)
                    samples.frombytes(buffer)
                    yield samples
        finally:
            lib.drwav_uninit(wav)


def wav_write_file(filename: str, sound: DecodedSoundFile) -> None:
    """Writes the pcm sound to a WAV file"""
    with ffi.new("drwav_data_format*") as fmt, ffi.new("drwav*") as pwav:
        fmt.container = lib.drwav_container_riff
        fmt.format = sound.sub_format or lib.DR_WAVE_FORMAT_PCM
        fmt.channels = sound.nchannels
        fmt.sampleRate = sound.sample_rate
        fmt.bitsPerSample = sound.sample_width * 8
        # what about floating point format?
        filename_bytes = filename.encode(sys.getfilesystemencoding())
        if not lib.drwav_init_file_write_sequential(pwav, filename_bytes,
                                                    fmt, sound.num_frames * sound.nchannels, ffi.NULL):
            raise IOError("can't open file for writing")
        try:
            lib.drwav_write_pcm_frames(pwav, sound.num_frames, sound.samples.tobytes())
        finally:
            lib.drwav_uninit(pwav)


def _create_int_array(itemsize: int) -> array.array:
    for typecode in "Bhilq":
        a = array.array(typecode)
        if a.itemsize == itemsize:
            return a
    raise ValueError("cannot create array")


def _get_filename_bytes(filename: str) -> bytes:
    filename2 = os.path.expanduser(filename)
    if not os.path.isfile(filename2):
        raise FileNotFoundError(filename)
    return filename2.encode(sys.getfilesystemencoding())


class Devices:
    """Query the audio playback and record devices that miniaudio provides"""
    def __init__(self, backends: Optional[List[Backend]] = None) -> None:
        self._context = ffi.NULL
        context = ffi.new("ma_context*")
        if backends:
            backends_mem = ffi.new("ma_backend[]", len(backends))
            for i, b in enumerate(backends):
                backends_mem[i] = b.value
            result = lib.ma_context_init(backends_mem, len(backends), ffi.NULL, context)
        else:
            result = lib.ma_context_init(ffi.NULL, 0, ffi.NULL, context)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("cannot init context", result)
        self._context = context
        self.backend = ffi.string(lib.ma_get_backend_name(self._context[0].backend)).decode()

    def get_playbacks(self) -> List[Dict[str, Any]]:
        """Get a list of playback devices and some details about them"""
        with ffi.new("ma_device_info**") as playback_infos, ffi.new("ma_uint32*") as playback_count:
            result = lib.ma_context_get_devices(self._context, playback_infos, playback_count, ffi.NULL,  ffi.NULL)
            if result != lib.MA_SUCCESS:
                raise MiniaudioError("cannot get device infos", result)
            devs = []
            for i in range(playback_count[0]):
                ma_device_info = playback_infos[0][i]
                dev_id = ffi.new("ma_device_id *", ma_device_info.id)  # copy the id memory
                info = {
                    "name": ffi.string(ma_device_info.name).decode(),
                    "type": DeviceType.PLAYBACK,
                    "id": dev_id
                }
                info.update(self._get_info(DeviceType.PLAYBACK, ma_device_info))
                devs.append(info)
            return devs

    def get_captures(self) -> List[Dict[str, Any]]:
        """Get a list of capture devices and some details about them"""
        with ffi.new("ma_device_info**") as capture_infos, ffi.new("ma_uint32*") as capture_count:
            result = lib.ma_context_get_devices(self._context, ffi.NULL,  ffi.NULL, capture_infos, capture_count)
            if result != lib.MA_SUCCESS:
                raise MiniaudioError("cannot get device infos", result)
            devs = []
            for i in range(capture_count[0]):
                ma_device_info = capture_infos[0][i]
                dev_id = ffi.new("ma_device_id *", ma_device_info.id)  # copy the id memory
                info = {
                    "name": ffi.string(ma_device_info.name).decode(),
                    "type": DeviceType.CAPTURE,
                    "id": dev_id
                }
                info.update(self._get_info(DeviceType.CAPTURE, ma_device_info))
                devs.append(info)
            return devs

    def _get_info(self, device_type: DeviceType, device_info: ffi.CData) -> Dict[str, Any]:
        # obtain detailed info about the device
        result = lib.ma_context_get_device_info(self._context, device_type.value, ffi.addressof(device_info.id), ffi.addressof(device_info))
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("can't get device info")
        formats = []
        for fmt in range(device_info.nativeDataFormatCount):
            data_format = device_info.nativeDataFormats[fmt]
            formats.append({
                "format": ffi.string(lib.ma_get_format_name(data_format.format)).decode(),
                "samplerate": data_format.sampleRate,
                "channels": data_format.channels
            })
        return {"formats": formats}

    def __del__(self):
        lib.ma_context_uninit(self._context)


def width_from_format(sampleformat: SampleFormat) -> int:
    """returns the sample width in bytes, of the given sample format."""
    widths = {
        SampleFormat.UNKNOWN: 0,
        SampleFormat.UNSIGNED8: 1,
        SampleFormat.SIGNED16: 2,
        SampleFormat.SIGNED24: 3,
        SampleFormat.SIGNED32: 4,
        SampleFormat.FLOAT32: 4
    }
    if sampleformat in widths:
        return widths[sampleformat]
    raise MiniaudioError("unsupported sample format", sampleformat)


def _array_proto_from_format(sampleformat: SampleFormat) -> array.array:
    arrays = {
        SampleFormat.UNSIGNED8: _create_int_array(1),
        SampleFormat.SIGNED16: _create_int_array(2),
        SampleFormat.SIGNED32: _create_int_array(4),
        SampleFormat.FLOAT32: array.array('f')
    }
    if sampleformat in arrays:
        return arrays[sampleformat]
    raise MiniaudioError("the requested sample format can not be used directly: "
                         + sampleformat.name + " (convert it first)")


def _format_from_width(sample_width: int, is_float: bool = False) -> SampleFormat:
    if is_float:
        return SampleFormat.FLOAT32
    elif sample_width == 1:
        return SampleFormat.UNSIGNED8
    elif sample_width == 2:
        return SampleFormat.SIGNED16
    elif sample_width == 3:
        return SampleFormat.SIGNED24
    elif sample_width == 4:
        return SampleFormat.SIGNED32
    elif sample_width == 0:
        return SampleFormat.UNKNOWN
    else:
        raise MiniaudioError("unsupported sample width", sample_width)


def decode_file(filename: str, output_format: SampleFormat = SampleFormat.SIGNED16,
                nchannels: int = 2, sample_rate: int = 44100, dither: DitherMode = DitherMode.NONE) -> DecodedSoundFile:
    """Convenience function to decode any supported audio file to raw PCM samples in your chosen format."""
    sample_width = width_from_format(output_format)
    samples = _array_proto_from_format(output_format)
    filenamebytes = _get_filename_bytes(filename)
    with ffi.new("ma_uint64 *") as frames, ffi.new("void **") as memory:
        decoder_config = lib.ma_decoder_config_init(output_format.value, nchannels, sample_rate)
        decoder_config.ditherMode = dither.value
        result = lib.ma_decode_file(filenamebytes, ffi.addressof(decoder_config), frames, memory)
        if result != lib.MA_SUCCESS:
            raise DecodeError("failed to decode file", result)
        buffer = ffi.buffer(memory[0], frames[0] * nchannels * sample_width)
        samples.frombytes(buffer)
        lib.ma_free(memory[0], ffi.NULL)
        return DecodedSoundFile(filename, nchannels, sample_rate, output_format, samples)


def decode(data: bytes, output_format: SampleFormat = SampleFormat.SIGNED16,
           nchannels: int = 2, sample_rate: int = 44100, dither: DitherMode = DitherMode.NONE) -> DecodedSoundFile:
    """Convenience function to decode any supported audio file in memory to raw PCM samples in your chosen format."""
    sample_width = width_from_format(output_format)
    samples = _array_proto_from_format(output_format)
    with ffi.new("ma_uint64 *") as frames, ffi.new("void **") as memory:
        decoder_config = lib.ma_decoder_config_init(output_format.value, nchannels, sample_rate)
        decoder_config.ditherMode = dither.value
        result = lib.ma_decode_memory(data, len(data), ffi.addressof(decoder_config), frames, memory)
        if result != lib.MA_SUCCESS:
            raise DecodeError("failed to decode data", result)
        buffer = ffi.buffer(memory[0], frames[0] * nchannels * sample_width)
        samples.frombytes(buffer)
        lib.ma_free(memory[0], ffi.NULL)
        return DecodedSoundFile("<memory>", nchannels, sample_rate, output_format, samples)


def _samples_stream_generator(frames_to_read: int, nchannels: int, output_format: SampleFormat,
                              decoder: ffi.CData, data: Any,
                              on_close: Optional[Callable] = None) -> Generator[array.array, int, None]:
    _reference = data    # make sure any data passed in is not garbage collected
    sample_width = width_from_format(output_format)
    samples_proto = _array_proto_from_format(output_format)
    allocated_buffer_frames = max(frames_to_read, 16384)
    try:
        with ffi.new("int8_t[]", allocated_buffer_frames * nchannels * sample_width) as decodebuffer:
            buf_ptr = ffi.cast("void *", decodebuffer)
            want_frames = (yield samples_proto) or frames_to_read
            source = None     # type: Optional[StreamableSource]
            if decoder.pUserData != ffi.NULL:
                source = ffi.from_handle(decoder.pUserData)
            while True:
                if want_frames > allocated_buffer_frames:
                    raise MiniaudioError("wanted to read more frames than storage was allocated for ({} vs {})"
                                         .format(want_frames, allocated_buffer_frames))
                num_frames = 0
                with ffi.new("ma_uint64 *") as frames_read:
                    try:
                        result = lib.ma_decoder_read_pcm_frames(decoder, buf_ptr, want_frames, frames_read)
                    except Exception as x:
                        raise DecodeError("error in ma_decoder_read_pcm_frames") from x
                    else:
                        if result == lib.MA_SUCCESS:
                            num_frames = frames_read[0]
                        elif result == lib.MA_AT_END:
                            break
                        else:
                            raise DecodeError("error in ma_decoder_read_pcm_frames")
                if num_frames <= 0:
                    break
                if source and source.error_in_readcallback:
                    raise DecodeError("error in read callback") from source.error_in_readcallback
                buffer = ffi.buffer(decodebuffer, num_frames * sample_width * nchannels)
                samples = array.array(samples_proto.typecode)
                samples.frombytes(buffer)
                want_frames = (yield samples) or frames_to_read
    finally:
        if on_close:
            on_close()
        lib.ma_decoder_uninit(decoder)


def stream_file(filename: str, output_format: SampleFormat = SampleFormat.SIGNED16, nchannels: int = 2,
                sample_rate: int = 44100, frames_to_read: int = 1024,
                dither: DitherMode = DitherMode.NONE, seek_frame: int = 0) -> Generator[array.array, int, None]:
    """
    Convenience generator function to decode and stream any supported audio file
    as chunks of raw PCM samples in the chosen format.
    If you send() a number into the generator rather than just using next() on it,
    you'll get that given number of frames, instead of the default configured amount.
    This is particularly useful to plug this stream into an audio device callback that
    wants a variable number of frames per call.
    """
    filenamebytes = _get_filename_bytes(filename)
    decoder = ffi.new("ma_decoder *")
    decoder_config = lib.ma_decoder_config_init(output_format.value, nchannels, sample_rate)
    decoder_config.ditherMode = dither.value
    result = lib.ma_decoder_init_file(filenamebytes, ffi.addressof(decoder_config), decoder)
    if result != lib.MA_SUCCESS:
        raise DecodeError("failed to init decoder", result)
    if seek_frame > 0:
        result = lib.ma_decoder_seek_to_pcm_frame(decoder, seek_frame)
        if result != lib.MA_SUCCESS:
            raise DecodeError("failed to seek to frame", result)
    g = _samples_stream_generator(frames_to_read, nchannels, output_format, decoder, None)
    dummy = next(g)
    assert len(dummy) == 0
    return g


def stream_memory(data: bytes, output_format: SampleFormat = SampleFormat.SIGNED16, nchannels: int = 2,
                  sample_rate: int = 44100, frames_to_read: int = 1024,
                  dither: DitherMode = DitherMode.NONE) -> Generator[array.array, int, None]:
    """
    Convenience generator function to decode and stream any supported audio file in memory
    as chunks of raw PCM samples in the chosen format.
    If you send() a number into the generator rather than just using next() on it,
    you'll get that given number of frames, instead of the default configured amount.
    This is particularly useful to plug this stream into an audio device callback that
    wants a variable number of frames per call.
    """
    decoder = ffi.new("ma_decoder *")
    decoder_config = lib.ma_decoder_config_init(output_format.value, nchannels, sample_rate)
    decoder_config.ditherMode = dither.value
    result = lib.ma_decoder_init_memory(data, len(data), ffi.addressof(decoder_config), decoder)
    if result != lib.MA_SUCCESS:
        raise DecodeError("failed to init decoder", result)
    g = _samples_stream_generator(frames_to_read, nchannels, output_format, decoder, data)
    dummy = next(g)
    assert len(dummy) == 0
    return g


def stream_raw_pcm_memory(pcmdata: Union[array.array, memoryview, bytes],
                          nchannels: int, sample_width: int,
                          frames_to_read: int = 4096) -> PlaybackCallbackGeneratorType:
    """
    Convenience generator function to stream raw pcm audio data from memory.
    Usually you don't need to use this as the library provides many other streaming
    options that work on much smaller, encoded, audio data.
    However, in the odd case that you only have already decoded raw pcm data you can use
    this generator as a stream source.

    The data can be provided in ``array`` type or ``bytes``, ``memoryview`` or even a numpy array.
    Be sure to also specify the correct number of channels that the audio data has, and the
    sample with in bytes.
    """
    def _mem_stream_gen() -> PlaybackCallbackGeneratorType:
        nonlocal sample_width
        # sample_width should be provided if the data is not an array.array, but a bytes type instead.
        if type(pcmdata) is array.array:
            sample_width = 1   # array.array frames already yield the correct data size
        memdata = memoryview(pcmdata)
        required_frames = (yield b"") or frames_to_read  # generator initialization
        frames = 0
        while frames < len(memdata):
            frames_end = frames + required_frames * nchannels * sample_width
            required_frames = (yield memdata[frames:frames_end]) or frames_to_read
            frames = frames_end
    g = _mem_stream_gen()
    dummy = next(g)  # start the generator
    assert len(dummy) == 0
    return g


class StreamableSource(abc.ABC):
    """Base class for streams of audio data bytes. Can be used as a contextmanager, to properly call close()."""
    ffi_handle = ffi.NULL               # can be set later
    error_in_readcallback = None        # type: Exception

    @abc.abstractmethod
    def read(self, num_bytes: int) -> Union[bytes, memoryview]:
        """override this to provide data bytes to the consumer of the stream"""
        pass

    def seek(self, offset: int, origin: SeekOrigin) -> bool:
        """
        Override this if the stream supports seeking.
        Note: seek support is sometimes not needed if you give the file type
        to a decoder upfront. You can ignore this method then.
        """
        return False

    def close(self) -> None:
        """Override this to properly close the stream and free resources."""
        pass

    def __enter__(self) -> "StreamableSource":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class IceCastClient(StreamableSource):
    """
    A simple client for IceCast audio streams as miniaudio streamable source.
    If the stream has Icy MetaData, the stream_title attribute will be updated
    with the actual title taken from the metadata.
    You can also provide a callback to be called when a new stream title is available.
    The downloading of the data from the internet is done in a background thread
    and it tries to keep a (small) buffer filled with available data to read.
    You can optionally provide a custom ssl.SSLContext in the ssl_context parameter,
    if you need to change the way SSL connections are configured (certificates, checks, etc).
    """

    BLOCK_SIZE = 8*1024
    BUFFER_SIZE = 64*1024

    def __init__(self, url: str, update_stream_title: Callable[['IceCastClient', str], None] = None,
                 ssl_context: "ssl.SSLContext" = None) -> None:
        self.url = url
        self.stream_title = "???"
        self.station_genre = "???"
        self.station_name = "???"
        self.audio_info = ""
        self.audio_format = FileFormat.UNKNOWN
        self._stop_stream = False
        self._buffer = b""
        self._buffer_lock = threading.Lock()
        self._update_title = update_stream_title
        req = urllib.request.Request(url, headers={"icy-metadata": "1"})
        with urllib.request.urlopen(req, context=ssl_context) as result:
            self.station_genre = result.headers["icy-genre"]
            self.station_name = result.headers["icy-name"]
            stream_format = result.headers["Content-Type"]
            self.audio_format = self.determine_audio_format(stream_format)
        self._download_thread = threading.Thread(target=self._download_stream, daemon=True)
        self._download_thread.start()

    def determine_audio_format(self, stream_format: str) -> FileFormat:
        if stream_format == "audio/mpeg":
            return FileFormat.MP3
        elif stream_format == "audio/flac":
            return FileFormat.FLAC
        elif stream_format.endswith("/ogg"):
            return FileFormat.VORBIS
        else:
            return FileFormat.UNKNOWN

    def read(self, num_bytes: int) -> bytes:
        """Read a chunk of data from the stream."""
        while len(self._buffer) < num_bytes:
            time.sleep(0.1)
        with self._buffer_lock:
            chunk = self._buffer[:num_bytes]
            self._buffer = self._buffer[num_bytes:]
            return chunk

    def close(self) -> None:
        """Stop the stream, aborting the background downloading."""
        self._stop_stream = True
        self._download_thread.join()

    def _readall(self, fileobject, size: int) -> bytes:
        b = b""
        while len(b) < size:
            b += fileobject.read(size)
        return b

    def _download_stream(self) -> None:
        req = urllib.request.Request(self.url, headers={"icy-metadata": "1"})
        with urllib.request.urlopen(req) as result:
            self.station_genre = result.headers["icy-genre"]
            self.station_name = result.headers["icy-name"]
            stream_format = result.headers["Content-Type"]
            if stream_format:
                self.audio_format = self.determine_audio_format(stream_format)
            self.audio_info = result.headers.get("ice-audio-info", "")
            if "icy-metaint" in result.headers:
                meta_interval = int(result.headers["icy-metaint"])
            else:
                meta_interval = 0
            if meta_interval:
                # note: the meta_interval is fixed for the entire stream, so just use that as chunk size
                while not self._stop_stream:
                    while len(self._buffer) >= self.BUFFER_SIZE:
                        time.sleep(0.2)
                        if self._stop_stream:
                            return
                    chunk = self._readall(result, meta_interval)
                    with self._buffer_lock:
                        self._buffer += chunk
                    meta_size = 16 * self._readall(result, 1)[0]
                    metadata = str(self._readall(result, meta_size).strip(b"\0"), "utf-8", errors="replace")
                    if metadata:
                        meta = self.parse_metadata(metadata)
                        stream_title = meta.get("StreamTitle")
                        if stream_title:
                            self.stream_title = stream_title
                            if self._update_title:
                                self._update_title(self, stream_title)
            else:
                while not self._stop_stream:
                    while len(self._buffer) >= self.BUFFER_SIZE:
                        time.sleep(0.2)
                        if self._stop_stream:
                            return
                    chunk = result.read(self.BLOCK_SIZE)
                    with self._buffer_lock:
                        self._buffer += chunk

    @staticmethod
    def parse_metadata(metadata: str) -> Dict[str, str]:
        meta = {}
        for part in metadata.split(';'):
            key, _, value = part.partition('=')
            if key:
                meta[key] = value.strip("'")
        return meta


def stream_any(source: StreamableSource, source_format: FileFormat = FileFormat.UNKNOWN,
               output_format: SampleFormat = SampleFormat.SIGNED16, nchannels: int = 2,
               sample_rate: int = 44100, frames_to_read: int = 1024,
               dither: DitherMode = DitherMode.NONE, seek_frame: int = 0) -> Generator[array.array, int, None]:
    """
    Convenience function that returns a generator to decode and stream any source of encoded audio data
    (such as a network stream). Stream result is chunks of raw PCM samples in the chosen format.
    If you send() a number into the generator rather than just using next() on it,
    you'll get that given number of frames, instead of the default configured amount.
    This is particularly useful to plug this stream into an audio device callback that
    wants a variable number of frames per call.
    """
    decoder = ffi.new("ma_decoder *")
    decoder_config = lib.ma_decoder_config_init(output_format.value, nchannels, sample_rate)
    decoder_config.ditherMode = dither.value
    source.ffi_handle = ffi.new_handle(source)
    decoder_config.encodingFormat = source_format.value
    result = lib.ma_decoder_init(lib._internal_decoder_read_callback, lib._internal_decoder_seek_callback,
                          source.ffi_handle, ffi.addressof(decoder_config), decoder)
    if result != lib.MA_SUCCESS:
        raise DecodeError("failed to init decoder", result)
    if seek_frame > 0:
        result = lib.ma_decoder_seek_to_pcm_frame(decoder, seek_frame)
        if result != lib.MA_SUCCESS:
            raise DecodeError("failed to seek to frame", result)

    def on_close() -> None:
        pass

    g = _samples_stream_generator(frames_to_read, nchannels, output_format, decoder, None, on_close)
    dummy = next(g)
    assert len(dummy) == 0
    return g


def stream_with_callbacks(sample_stream: PlaybackCallbackGeneratorType,
                          progress_callback: Union[Callable[[int], None], None] = None,
                          frame_process_method: Union[Callable[[FramesType], FramesType], None] = None,
                          end_callback: Union[Callable, None] = None) -> PlaybackCallbackGeneratorType:
    """
    Convenience generator function to add callback and processing functionality to another stream.
    You can specify :
    > A callback function that gets called during play and takes an int
    for the number of frames played.

    > A function that can be used to process raw data frames before they are yielded back
    (takes an array.array or bytes, returns an array.array or bytes)
    *Note: if the processing method is slow it will result in audio glitchiness

    > A callback function that gets called when the stream ends playing.
    """
    frame_count = yield b""
    try:
        while True:
            frame = sample_stream.send(frame_count)
            if frame_process_method:
                frame_count = yield frame_process_method(frame)
            else:
                frame_count = yield frame
            if progress_callback:
                progress_callback(frame_count)
    except StopIteration:
        if end_callback:
            end_callback()


@ffi.def_extern()
def _internal_decoder_read_callback(decoder: ffi.CData, output: ffi.CData, num_bytes: int, bytes_read: ffi.CData) -> int:
    bytes_read[0] = 0
    if num_bytes <= 0 or not decoder.pUserData:
        return lib.MA_ERROR
    source = ffi.from_handle(decoder.pUserData)   # type: StreamableSource
    if source.error_in_readcallback is None:
        try:
            data = source.read(num_bytes)
            ffi.memmove(output, data, len(data))
            bytes_read[0] = len(data)
            return lib.MA_SUCCESS if len(data) > 0 else lib.MA_AT_END
        except Exception as x:
            source.error_in_readcallback = x
    return lib.MA_ERROR


@ffi.def_extern()
def _internal_decoder_seek_callback(decoder: ffi.CData, offset: int, seek_origin: int) -> int:
    if not decoder.pUserData:
        return lib.MA_ERROR
    if offset == 0 and seek_origin == lib.ma_seek_origin_current:
        return lib.MA_SUCCESS
    source = ffi.from_handle(decoder.pUserData)
    return lib.MA_SUCCESS if int(source.seek(offset, SeekOrigin(seek_origin))) else lib.MA_BAD_SEEK


def convert_sample_format(from_fmt: SampleFormat, sourcedata: bytes, to_fmt: SampleFormat,
                          dither: DitherMode = DitherMode.NONE) -> bytearray:
    """Convert a raw buffer of pcm samples to another sample format.
    The result is returned as another raw pcm sample buffer"""
    sample_width = width_from_format(from_fmt)
    num_samples = len(sourcedata) // sample_width
    sample_width = width_from_format(to_fmt)
    buffer = bytearray(sample_width * num_samples)
    lib.ma_pcm_convert(ffi.from_buffer(buffer), to_fmt.value, sourcedata, from_fmt.value, num_samples, dither.value)
    return buffer


def convert_frames(from_fmt: SampleFormat, from_numchannels: int, from_samplerate: int, sourcedata: bytes,
                   to_fmt: SampleFormat, to_numchannels: int, to_samplerate: int) -> bytearray:
    """Convert audio frames in source sample format with a certain number of channels,
    to another sample format and possibly down/upmixing the number of channels as well."""
    sample_width = width_from_format(from_fmt)
    num_frames = int(len(sourcedata) / from_numchannels / sample_width)
    sample_width = width_from_format(to_fmt)
    output_frame_count = lib.ma_calculate_frame_count_after_resampling(to_samplerate, from_samplerate, num_frames)
    buffer = bytearray(output_frame_count * sample_width * to_numchannels)
    # note: the API doesn't have an option here to specify the dither mode.
    lib.ma_convert_frames(ffi.from_buffer(buffer), output_frame_count, to_fmt.value, to_numchannels, to_samplerate,
                          sourcedata, num_frames, from_fmt.value, from_numchannels, from_samplerate)
    return buffer


@ffi.def_extern()
def _internal_data_callback(device: ffi.CData, output: ffi.CData, input: ffi.CData, framecount: int) -> None:
    if framecount <= 0 or not device.pUserData:
        return
    callback_device = ffi.from_handle(device.pUserData)
    callback_device._data_callback(device, output, input, framecount)


@ffi.def_extern()
def _internal_stop_callback(device: ffi.CData) -> None:
    if not device.pUserData:
        return
    callback_device = ffi.from_handle(device.pUserData)
    callback_device._stop_callback(device)


class AbstractDevice:
    def __init__(self) -> None:
        self.callback_generator = None          # type: Optional[GeneratorTypes]
        self.running = False
        self.stop_callback = None               # doesn't work consistently
        self._device = ffi.new("ma_device *")

    def __del__(self) -> None:
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self, callback_generator: GeneratorTypes) -> None:
        """Start playback or capture, using the given callback generator (should already been started)"""
        if self.callback_generator:
            raise MiniaudioError("can't start an already started device")
        if not inspect.isgenerator(callback_generator):
            raise TypeError("callback must be a generator", type(callback_generator))
        self.callback_generator = callback_generator
        result = lib.ma_device_start(self._device)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("failed to start audio device", result)
        self.running = True

    def stop(self) -> None:
        """Halt playback or capture."""
        self.callback_generator = None
        if self.running:
            result = lib.ma_device_stop(self._device)
            if result != lib.MA_SUCCESS:
                raise MiniaudioError("failed to stop audio device", result)
        self.running = False

    def close(self) -> None:
        """
        Halt playback or capture and close down the device.
        If you use the device as a context manager, it will be closed automatically.
        """
        try:
            self.stop()
        except MiniaudioError:
            pass
        if self._device is not None:
            lib.ma_device_uninit(self._device)
            self._device = None
        self.stop_callback = None

    def _stop_callback(self, device: ffi.CData) -> None:
        """Called when the device is stopped (i.e. device disconnect or manual stop) Doesn't work consistently however."""
        if self.stop_callback:
            self.running = False
            self.stop_callback()
            self.callback_generator = None

    def _make_context(self, backends: List[Backend], thread_prio: ThreadPriority = ThreadPriority.HIGHEST,
                      app_name: str = "") -> ffi.CData:
        context_config = lib.ma_context_config_init()
        context_config.threadPriority = thread_prio.value
        context = ffi.new("ma_context*")
        if app_name:
            self._context_app_name = app_name.encode()
            context_config.pulse.pApplicationName = ffi.from_buffer(self._context_app_name)
            context_config.jack.pClientName = ffi.from_buffer(self._context_app_name)
        if backends:
            # use a context to supply a preferred backend list
            backends_mem = ffi.new("ma_backend[]", len(backends))
            for i, b in enumerate(backends):
                backends_mem[i] = b.value
            result = lib.ma_context_init(backends_mem, len(backends), ffi.addressof(context_config), context)
            if result != lib.MA_SUCCESS:
                raise MiniaudioError("cannot init context", result)
        else:
            result = lib.ma_context_init(ffi.NULL, 0, ffi.addressof(context_config), context)
            if result != lib.MA_SUCCESS:
                raise MiniaudioError("cannot init context", result)
        return context


class CaptureDevice(AbstractDevice):
    """An audio device provided by miniaudio, for audio capture (recording)."""
    def __init__(self, input_format: SampleFormat = SampleFormat.SIGNED16, nchannels: int = 2,
                 sample_rate: int = 44100, buffersize_msec: int = 200, device_id: Union[ffi.CData, None] = None,
                 callback_periods: int = 0, backends: Optional[List[Backend]] = None,
                 thread_prio: ThreadPriority = ThreadPriority.HIGHEST, app_name: str = "") -> None:
        super().__init__()
        self.format = input_format
        self.sample_width = width_from_format(input_format)
        self.nchannels = nchannels
        self.sample_rate = sample_rate
        self.buffersize_msec = buffersize_msec
        self._ffi_handle = ffi.new_handle(self)
        self._devconfig = lib.ma_device_config_init(lib.ma_device_type_capture)
        self._devconfig.sampleRate = self.sample_rate
        self._devconfig.capture.channels = self.nchannels
        self._devconfig.capture.format = self.format.value
        self._devconfig.capture.pDeviceID = device_id or ffi.NULL
        self._devconfig.periodSizeInMilliseconds = self.buffersize_msec
        self._devconfig.pUserData = self._ffi_handle
        self._devconfig.dataCallback = lib._internal_data_callback
        self._devconfig.stopCallback = lib._internal_stop_callback
        self._devconfig.periods = callback_periods
        self.callback_generator = None  # type: Optional[CaptureCallbackGeneratorType]
        self._context = self._make_context(backends or [], thread_prio, app_name)
        result = lib.ma_device_init(self._context, ffi.addressof(self._devconfig), self._device)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("failed to init device", result)
        if self._device.pContext.backend == lib.ma_backend_null:
            if backends and Backend.NULL not in backends:
                raise MiniaudioError("no suitable audio backend found")
        self.backend = ffi.string(lib.ma_get_backend_name(self._device.pContext.backend)).decode()

    def start(self, callback_generator: CaptureCallbackGeneratorType) -> None:      # type: ignore
        """Start the audio device: capture (recording) begins.
        The recorded audio data is sent to the given callback generator as raw bytes.
        (it should already be started before)"""
        return super().start(callback_generator)

    def _data_callback(self, device: ffi.CData, output: ffi.CData, input: ffi.CData, framecount: int) -> None:
        if self.callback_generator:
            buffer_size = self.sample_width * self.nchannels * framecount
            data = bytearray(buffer_size)
            ffi.memmove(data, input, buffer_size)
            try:
                self.callback_generator.send(data)
            except StopIteration:
                self.callback_generator = None
                return
            except Exception:
                self.callback_generator = None
                raise


class PlaybackDevice(AbstractDevice):
    """An audio device provided by miniaudio, for audio playback."""
    def __init__(self, output_format: SampleFormat = SampleFormat.SIGNED16, nchannels: int = 2,
                 sample_rate: int = 44100, buffersize_msec: int = 200, device_id: Union[ffi.CData, None] = None,
                 callback_periods: int = 0, backends: Optional[List[Backend]] = None,
                 thread_prio: ThreadPriority = ThreadPriority.HIGHEST, app_name: str = "") -> None:
        super().__init__()
        self.format = output_format
        self.sample_width = width_from_format(output_format)
        self.nchannels = nchannels
        self.sample_rate = sample_rate
        self.buffersize_msec = buffersize_msec
        self._ffi_handle = ffi.new_handle(self)
        self._devconfig = lib.ma_device_config_init(lib.ma_device_type_playback)
        self._devconfig.sampleRate = self.sample_rate
        self._devconfig.playback.channels = self.nchannels
        self._devconfig.playback.format = self.format.value
        self._devconfig.playback.pDeviceID = device_id or ffi.NULL
        self._devconfig.periodSizeInMilliseconds = self.buffersize_msec
        self._devconfig.pUserData = self._ffi_handle
        self._devconfig.dataCallback = lib._internal_data_callback
        self._devconfig.stopCallback = lib._internal_stop_callback
        self._devconfig.periods = callback_periods
        self.callback_generator = None   # type: Optional[PlaybackCallbackGeneratorType]

        self._context = self._make_context(backends or [], thread_prio, app_name)
        result = lib.ma_device_init(self._context, ffi.addressof(self._devconfig), self._device)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("failed to init device", result)
        if self._device.pContext.backend == lib.ma_backend_null:
            if backends and Backend.NULL not in backends:
                raise MiniaudioError("no suitable audio backend found")
        self.backend = ffi.string(lib.ma_get_backend_name(self._device.pContext.backend)).decode()

    def start(self, callback_generator: PlaybackCallbackGeneratorType) -> None:     # type: ignore
        """Start the audio device: playback begins. The audio data is provided by the given callback generator.
        The generator gets sent the required number of frames and should yield the sample data
        as raw bytes, a memoryview, an array.array, or as a numpy array with shape (numframes, numchannels).
        The generator should already be started before passing it in."""
        return super().start(callback_generator)

    def _data_callback(self, device: ffi.CData, output: ffi.CData, input: ffi.CData, framecount: int) -> None:
        if self.callback_generator:
            try:
                samples = self.callback_generator.send(framecount)
            except StopIteration:
                self.callback_generator = None
                return
            except Exception:
                self.callback_generator = None
                raise
            samples_bytes = _bytes_from_generator_samples(samples)
            if samples_bytes:
                if len(samples_bytes) > framecount * self.sample_width * self.nchannels:
                    self.callback_generator = None
                    raise MiniaudioError("number of frames from callback exceeds maximum")
                ffi.memmove(output, samples_bytes, len(samples_bytes))


class DuplexStream(AbstractDevice):
    """Joins a capture device and a playback device."""
    def __init__(self, playback_format: SampleFormat = SampleFormat.SIGNED16,
                 playback_channels: int = 2, capture_format: SampleFormat = SampleFormat.SIGNED16,
                 capture_channels: int = 2, sample_rate: int = 44100, buffersize_msec: int = 200,
                 playback_device_id: Union[ffi.CData, None] = None, capture_device_id: Union[ffi.CData, None] = None,
                 callback_periods: int = 0, backends: Optional[List[Backend]] = None,
                 thread_prio: ThreadPriority = ThreadPriority.HIGHEST, app_name: str = "") -> None:
        super().__init__()
        self.capture_format = capture_format
        self.playback_format = playback_format
        self.sample_width = width_from_format(capture_format)
        self.capture_channels = capture_channels
        self.playback_channels = playback_channels
        self.sample_rate = sample_rate
        self.buffersize_msec = buffersize_msec
        self._ffi_handle = ffi.new_handle(self)
        self._devconfig = lib.ma_device_config_init(lib.ma_device_type_duplex)
        self._devconfig.sampleRate = self.sample_rate
        self._devconfig.playback.channels = self.playback_channels
        self._devconfig.playback.format = self.playback_format.value
        self._devconfig.playback.pDeviceID = playback_device_id or ffi.NULL
        self._devconfig.capture.channels = self.capture_channels
        self._devconfig.capture.format = self.capture_format.value
        self._devconfig.capture.pDeviceID = capture_device_id or ffi.NULL
        self._devconfig.periodSizeInMilliseconds = self.buffersize_msec
        self._devconfig.pUserData = self._ffi_handle
        self._devconfig.dataCallback = lib._internal_data_callback
        self._devconfig.stopCallback = lib._internal_stop_callback
        self._devconfig.periods = callback_periods
        self.callback_generator = None  # type: Optional[DuplexCallbackGeneratorType]
        self._context = self._make_context(backends or [], thread_prio, app_name)
        result = lib.ma_device_init(self._context, ffi.addressof(self._devconfig), self._device)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("failed to init device", result)
        if self._device.pContext.backend == lib.ma_backend_null:
            if backends and Backend.NULL not in backends:
                raise MiniaudioError("no suitable audio backend found")
        self.backend = ffi.string(lib.ma_get_backend_name(self._device.pContext.backend)).decode()

    def start(self, callback_generator: DuplexCallbackGeneratorType) -> None:       # type: ignore
        """Start the audio device: playback and capture begin.
        The audio data for playback is provided by the given callback generator, which is sent the
        recorded audio data at the same time.
        (it should already be started before passing it in)"""
        return super().start(callback_generator)

    def _data_callback(self, device: ffi.CData, output: ffi.CData, input: ffi.CData, framecount: int) -> None:
        buffer_size = self.sample_width * self.capture_channels * framecount
        in_data = bytearray(buffer_size)
        ffi.memmove(in_data, input, buffer_size)
        if self.callback_generator:
            try:
                out_data = self.callback_generator.send(in_data)
            except StopIteration:
                self.callback_generator = None
                return
            except Exception:
                self.callback_generator = None
                raise
            if out_data:
                samples_bytes = _bytes_from_generator_samples(out_data)
                ffi.memmove(output, samples_bytes, len(samples_bytes))


def _bytes_from_generator_samples(samples: Union[array.array, memoryview, bytes]) -> bytes:
    # convert any non-bytes generator result to raw bytes
    if isinstance(samples, array.array):
        return memoryview(samples).cast('B')       # type: ignore
    elif isinstance(samples, memoryview) and samples.itemsize != 1:
        return samples.cast('B')    # type: ignore
    elif numpy and isinstance(samples, numpy.ndarray):
        return samples.tobytes()
    return samples      # type: ignore


class WavFileReadStream(io.RawIOBase):
    """An IO stream that reads as a .wav file, and which gets its pcm samples from the provided producer"""
    def __init__(self, pcm_sample_gen: PlaybackCallbackGeneratorType, sample_rate: int, nchannels: int,
                 output_format: SampleFormat, max_frames: int = 0) -> None:
        self.sample_gen = pcm_sample_gen
        self.sample_rate = sample_rate
        self.nchannels = nchannels
        self.format = output_format
        self.max_frames = max_frames
        self.sample_width = width_from_format(output_format)
        self.max_bytes = (max_frames * nchannels * self.sample_width) or sys.maxsize
        self.bytes_done = 0
        # create WAVE header
        fmt = ffi.new("drwav_data_format*")
        fmt.container = lib.drwav_container_riff
        fmt.format = lib.DR_WAVE_FORMAT_PCM
        fmt.channels = nchannels
        fmt.sampleRate = sample_rate
        fmt.bitsPerSample = self.sample_width * 8
        data = ffi.new("void**")
        datasize = ffi.new("size_t *")
        pwav = ffi.new("drwav*")
        if max_frames > 0:
            lib.drwav_init_memory_write_sequential(pwav, data, datasize, fmt, max_frames * nchannels, ffi.NULL)
        else:
            lib.drwav_init_memory_write(pwav, data, datasize, fmt, ffi.NULL)
        lib.drwav_uninit(pwav)
        self.buffered = bytes(ffi.buffer(data[0], datasize[0]))
        lib.drwav_free(data[0], ffi.NULL)

    def read(self, amount: int = sys.maxsize) -> Optional[bytes]:
        """Read up to the given amount of bytes from the file."""
        if self.bytes_done >= self.max_bytes or not self.sample_gen:
            return b""
        while len(self.buffered) < amount:
            try:
                samples = next(self.sample_gen)
            except StopIteration:
                self.bytes_done = sys.maxsize
                break
            else:
                self.buffered += _bytes_from_generator_samples(samples)
        result = self.buffered[:amount]
        self.buffered = self.buffered[amount:]
        self.bytes_done += len(result)
        return result

    def close(self) -> None:
        """Close the file"""
        pass


# miscellaneous

def lib_version() -> str:
    """Returns the version string of the underlying miniaudio C library"""
    return ffi.string(lib.ma_version_string()).decode()


def is_backend_enabled(backend: Backend) -> bool:
    """Determines whether or not the given backend is available by the compilation environment for the underlying miniaudio C library"""
    return bool(lib.ma_is_backend_enabled(backend.value))


def get_enabled_backends() -> Set[Backend]:
    """Returns the set of available backends by the compilation environment for the underlying miniaudio C library"""
    with ffi.new("size_t *") as count, ffi.new("ma_backend[30]") as backends:
        result = lib.ma_get_enabled_backends(backends, 30, count)
        if result != lib.MA_SUCCESS:
            raise MiniaudioError("can't determine enabled backends")
        return set(Backend(b) for b in backends[0:count[0]])


def is_loopback_supported(backend: Backend) -> bool:
    """Determines whether or not loopback mode is support by a backend."""
    return bool(lib.ma_is_loopback_supported(backend.value))
