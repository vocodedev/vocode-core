from threading import Lock

import json
import os
from typing import Union, Callable


def file_to_str(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def str_to_file(s: str, filepath):
    with open(filepath, "w") as f:
        f.write(s)


def dict_to_json_file(d: Union[dict, list], file_path: str):
    # TODO alternatively use pd.io.json
    str_to_file(json.dumps(d), file_path)


def json_file_to_dict(file_path: str):
    with open(file_path, 'r') as file:
        return json.load(file)


class JsonCacheProxy:

    DEFAULT_CACHE_STORAGE_PATH = os.path.dirname(os.path.abspath(__file__)) + '/cache/'
    LOCK = Lock()

    def __init__(self, name: str, func: Callable, postprocess_func: Callable = lambda x: x,
                 cache_storage_path=DEFAULT_CACHE_STORAGE_PATH):
        self.postprocess_func = postprocess_func

        if not os.path.exists(cache_storage_path):
            # create the directory
            os.makedirs(cache_storage_path)

        self.filepath = f'{cache_storage_path}/{name}-cache.json'
        self.cache = {}
        self.func = func
        if os.path.exists(self.filepath) and os.path.getsize(self.filepath) > 0:
            self.cache = json_file_to_dict(self.filepath)

    def __call__(self, key):
        return self.get(key)

    def get(self, key):
        with self.LOCK:
            value = self.cache.get(key, None)
            if value is None:
                value = self.func(key)
                self.set(key, value)

        return self.postprocess_func(value)

    def set(self, key, value):
        self.cache[key] = value
        dict_to_json_file(self.cache, self.filepath)

    def remove(self, key):
        with self.LOCK:
            if key in self.cache:
                del self.cache[key]
                dict_to_json_file(self.cache, self.filepath)

    def dump_to_file(self):
        dict_to_json_file(self.cache, self.filepath)
