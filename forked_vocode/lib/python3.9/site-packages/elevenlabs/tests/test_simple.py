from .utils import no_api_key, repeat_test_without_api_key, use_play


def test_api_key():
    from elevenlabs import get_api_key

    assert get_api_key() is not None
    with no_api_key():
        assert get_api_key() is None
    assert get_api_key() is not None


@repeat_test_without_api_key
def test_voices():
    from elevenlabs import voices

    # Test that we can get all voices
    all_voices = voices()
    assert len(all_voices) > 0


@repeat_test_without_api_key
def test_generate():
    from elevenlabs import generate, play

    # Test that we can generate audio
    audio = generate(text="Test voice generation.")
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)


def test_generate_stream():
    from typing import Iterable

    from elevenlabs import generate, stream

    # Test that we can generate audio stream
    audio_stream = generate(text="Test voice streaming.", stream=True)
    assert isinstance(audio_stream, Iterable)

    if use_play:
        audio = stream(audio_stream)
        assert isinstance(audio, bytes) and len(audio) > 0


def test_generate_stream_optimized():
    from typing import Iterable

    from elevenlabs import generate, stream

    # Test that we can generate audio stream
    audio_stream = generate(
        text="Test voice streaming optimized latency.", stream=True, latency=4
    )
    assert isinstance(audio_stream, Iterable)

    if use_play:
        audio = stream(audio_stream)
        assert isinstance(audio, bytes) and len(audio) > 0


def test_generate_with_voice():
    from elevenlabs import generate, play, voices

    # Test voice with name
    audio = generate(text="Test voice with name.", voice="Rachel")
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)

    # Test voice with id
    audio = generate(
        text="Test voice with id.",
        voice="21m00Tcm4TlvDq8ikWAM",
    )
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)

    # Test voice with Voice object
    voice = voices()[2]
    audio = generate(text="Test voice with Voice object.", voice=voice)
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)


def test_generate_multilingual_v1():
    from elevenlabs import generate, play

    # Test multilingual model
    audio = generate(text="Prueba modelo multilingüe.", model="eleven_multilingual_v1")
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)
