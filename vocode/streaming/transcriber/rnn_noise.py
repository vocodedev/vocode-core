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

with wave.open('/Users/ruslanrozb/Desktop/output.wav', 'rb') as f:
    params = f.getparams()
    nchannels, sampwidth, framerate, nframes = params[:4]

    # Ensure the file is mono and 16-bit
    if nchannels != 1 or sampwidth != 2:
        raise ValueError("Wave file must be mono and 16-bit")

    # Initialize DenoiseState
    st = rnnoise.rnnoise_create(None)

    # Open the output file
    with wave.open('outpu2t.wav', 'wb') as fout:
        fout.setparams(params)

        # Process the wave file in chunks
        frame_size = rnnoise.rnnoise_get_frame_size()
        while True:
            # Read a chunk of data
            data = f.readframes(frame_size)
            if not data:
                break

            # Convert to floats
            in_buf = (c_float * frame_size)(*map(lambda x: x / 32768,
                                                 array('h', data)))

            # Allocate output buffer
            out_buf = (c_float * frame_size)()

            # Process the chunk
            rnnoise.rnnoise_process_frame(st, out_buf, in_buf)

            # Convert processed floats back to 16-bit integers
            out_data = array('h', map(lambda x: int(x * 32768), out_buf))

            # Write the processed chunk
            fout.writeframes(out_data.tobytes())

    # Clean up
    rnnoise.rnnoise_destroy(st)