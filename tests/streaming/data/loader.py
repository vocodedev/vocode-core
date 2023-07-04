import os


def get_audio_path(relative_path: str):
    return os.path.join(os.path.dirname(__file__), relative_path)
