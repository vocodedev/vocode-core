import wave
from ctypes import *
from ctypes.util import find_library
from array import array
# Load the rnnoise library
lib_path = find_library("rnnoise")
if not lib_path:
    raise Exception("rnnoise library not found")
rnnoise = CDLL(lib_path)

# Define the prototypes for the functions
rnnoise.rnnoise_get_frame_size.restype = c_int
rnnoise.rnnoise_get_frame_size.argtypes = []

rnnoise.rnnoise_create.restype = POINTER(c_void_p)  # Assuming we don't have the actual structure
rnnoise.rnnoise_create.argtypes = [POINTER(c_void_p)]

rnnoise.rnnoise_process_frame.restype = c_float
rnnoise.rnnoise_process_frame.argtypes = [POINTER(c_void_p), POINTER(c_float), POINTER(c_float)]

rnnoise.rnnoise_destroy.restype = None
rnnoise.rnnoise_destroy.argtypes = [POINTER(c_void_p)]

# Get the frame size
frame_size = rnnoise.rnnoise_get_frame_size()

import numpy as np
import wave
from ctypes import *

# Assuming rnnoise is already loaded and rnnoise_get_frame_size, rnnoise_create, rnnoise_destroy, and rnnoise_process_frame are set up

# Initialize the RNNoise state
st = rnnoise.rnnoise_create(None)
if not st:
    raise Exception("Failed to create RNNoise state")

# Open the WAV file
with wave.open('/Users/ruslanrozb/Desktop/twillio_w_noise.wav', 'rb') as f, wave.open('output.wav', 'wb') as fout:
    # Set the parameters for the output file
    fout.setparams(f.getparams())

    # Process the audio in chunks
    frame_size = rnnoise.rnnoise_get_frame_size()
    while True:
        # Read a frame of data
        frame_data = f.readframes(frame_size)
        if not frame_data:
            break

        # Convert to numpy array of int16
        in_buf = np.frombuffer(frame_data, dtype=np.int16)

        # Normalize the audio to the range of [-1, 1]
        in_buf = in_buf.astype(np.float32)
        # in_buf /= 32768

        # Create a ctypes array from the numpy array
        c_in_buf = in_buf.ctypes.data_as(POINTER(c_float))
        c_out_buf = (c_float * frame_size)()

        # Process the frame
        vad_prob = rnnoise.rnnoise_process_frame(st, c_out_buf, c_in_buf)

        # Convert the processed audio back to int16
        out_buf = np.ctypeslib.as_array(c_out_buf)
        # out_buf *= 32768
        out_buf = out_buf.astype(np.int16)

        # Write the processed data to the output file
        fout.writeframes(out_buf.tobytes())

# Clean up the RNNoise state
rnnoise.rnnoise_destroy(st)
