import os
import re
from typing import Iterator, Optional, Union

from .api import TTS, Model, Voice, VoiceClone, Voices
from .cache import VOICES_CACHE


def set_api_key(api_key: str) -> None:
    os.environ["ELEVEN_API_KEY"] = api_key


def get_api_key() -> Optional[str]:
    return os.environ.get("ELEVEN_API_KEY")


def voices() -> Voices:
    """Lists all voices in the API, if authenticated for the current user"""
    api_key = get_api_key()
    global VOICES_CACHE
    VOICES_CACHE = Voices.from_api(api_key) if api_key else VOICES_CACHE
    return VOICES_CACHE


def clone(**kwargs) -> Voice:
    return Voice.from_clone(VoiceClone(**kwargs))


def is_voice_id(val: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9]{20}$", val))


def generate(
    text: Union[str, Iterator[str]],
    api_key: Optional[str] = None,
    voice: Union[str, Voice] = VOICES_CACHE[2],  # Bella
    model: Union[str, Model] = "eleven_monolingual_v1",
    stream: bool = False,
    latency: int = 1,
    stream_chunk_size: int = 2048,
) -> Union[bytes, Iterator[bytes]]:

    if isinstance(voice, str):
        voice_str = voice
        # If voice is valid voice_id, use it
        if is_voice_id(voice):
            voice = Voice(voice_id=voice)
        # Otherwise, search voice by name
        else:
            # Check if voice is in cache
            voice = next((v for v in VOICES_CACHE if v.name == voice_str), None)  # type: ignore # noqa E501
            # If not, query API
            voice = next((v for v in voices() if v.name == voice_str), None) if not voice else voice  # type: ignore # noqa E501

        # Raise error if voice not found
        if not voice:
            raise ValueError(f"Voice '{voice_str}' not found.")

    if isinstance(model, str):
        model = Model(model_id=model)

    assert isinstance(voice, Voice)
    assert isinstance(model, Model)

    if stream:
        if isinstance(text, str):
            return TTS.generate_stream(
                text, voice, model, stream_chunk_size, api_key=api_key, latency=latency
            )  # noqa E501
        elif isinstance(text, Iterator):
            return TTS.generate_stream_input(text, voice, model, api_key=api_key)
    else:
        assert isinstance(text, str)
        return TTS.generate(text, voice, model, api_key=api_key)
