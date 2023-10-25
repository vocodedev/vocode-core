import os
import tempfile
from contextlib import contextmanager
from functools import wraps
from typing import Sequence

import requests  # type: ignore

use_play = "PLAY" in os.environ


@contextmanager
def no_api_key():
    api_key = os.environ.get("ELEVEN_API_KEY")
    del os.environ["ELEVEN_API_KEY"]
    yield
    os.environ["ELEVEN_API_KEY"] = api_key


def repeat_test_without_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Call the function without API key
        with no_api_key():
            func(*args, **kwargs)
        # Call the function with original arguments
        return func(*args, **kwargs)

    return wrapper


@contextmanager
def as_local_files(urls: Sequence[str]):
    """Util to download files from urls and return local file paths"""
    file_paths = []
    temp_files = []
    for url in urls:
        response = requests.get(url)
        temp_file = tempfile.NamedTemporaryFile()
        temp_file.write(response.content)
        file_paths.append(temp_file.name)
        temp_files.append(temp_file)
    yield file_paths
    # Remove the files
    for temp_file in temp_files:
        temp_file.close()
