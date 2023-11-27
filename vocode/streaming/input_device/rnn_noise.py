from ctypes import CDLL, POINTER, c_int, c_float, c_void_p
from ctypes.util import find_library

import numpy as np


class RNNoiseWrapper:
    def __init__(self):
        lib_path = find_library("rnnoise")
        if not lib_path:
            raise Exception("RNNoise library not found")
        self.rnnoise = CDLL(lib_path)

        # Set up function prototypes
        self.rnnoise.rnnoise_get_frame_size.restype = c_int
        self.rnnoise.rnnoise_create.restype = POINTER(c_void_p)
        self.rnnoise.rnnoise_process_frame.restype = c_float
        self.rnnoise.rnnoise_destroy.restype = None

        self.frame_size = self.rnnoise.rnnoise_get_frame_size()
        self.state = self.rnnoise.rnnoise_create(None)
        if not self.state:
            raise Exception("Failed to create RNNoise state")

    def process_frame(self, frame_data):
        in_buf = np.frombuffer(frame_data, dtype=np.int16).astype(np.float32)
        c_in_buf = in_buf.ctypes.data_as(POINTER(c_float))
        c_out_buf = (c_float * self.frame_size)()
        vad_prob = self.rnnoise.rnnoise_process_frame(self.state, c_out_buf, c_in_buf)
        out_buf = np.ctypeslib.as_array(c_out_buf).astype(np.int16)
        return out_buf.tobytes(), vad_prob

    def destroy(self):
        self.rnnoise.rnnoise_destroy(self.state)
