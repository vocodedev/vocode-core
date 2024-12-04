import ctypes
import pathlib

import numpy as np
from pydub import AudioSegment

from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber
from vocode.utils.whisper_cpp.helpers import transcribe
from vocode.utils.whisper_cpp.whisper_params import WhisperFullParams


class WhisperCPPTranscriber(BaseTranscriber):
    def __init__(self, libname: str, fname_model: str):
        self.libname = libname
        self.fname_model = fname_model

        # whisper cpp
        # load library and model
        libname = pathlib.Path().absolute() / self.libname  # type: ignore
        self.whisper = ctypes.CDLL(libname)

        # tell Python what are the return types of the functions
        self.whisper.whisper_init_from_file.restype = ctypes.c_void_p
        self.whisper.whisper_full_default_params.restype = WhisperFullParams
        self.whisper.whisper_full_get_segment_text.restype = ctypes.c_char_p

        # initialize whisper.cpp context
        self.ctx = self.whisper.whisper_init_from_file(self.fname_model.encode("utf-8"))

        # get default whisper parameters and adjust as needed
        self.params = self.whisper.whisper_full_default_params()
        self.params.print_realtime = False
        self.params.print_progress = False
        self.params.single_segment = True

    def transcribe(self, audio_segment: AudioSegment) -> str:
        transcription, _ = transcribe(
            self.whisper,
            self.params,
            self.ctx,
            audio_segment,
        )
        return transcription
