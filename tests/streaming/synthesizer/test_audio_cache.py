import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from pytest_mock import MockerFixture

from vocode.streaming.utils.singleton import Singleton


@pytest.fixture(autouse=True)
def cleanup_singleton_audio_cache():
    from vocode.streaming.synthesizer.audio_cache import AudioCache

    if AudioCache in Singleton._instances:
        del Singleton._instances[AudioCache]
    yield


@pytest.mark.asyncio
async def test_set_and_get(mocker: MockerFixture):
    from vocode.streaming.synthesizer.audio_cache import AudioCache

    fake_redis = FakeAsyncRedis()

    mocker.patch(
        "vocode.streaming.synthesizer.audio_cache.initialize_redis_bytes", return_value=fake_redis
    )

    cache = await AudioCache.safe_create()
    voice_identifier = "voice_id"
    text = "text"
    audio_data = b"chunk"

    assert await cache.get_audio(voice_identifier, text) is None

    await cache.set_audio(voice_identifier, text, audio_data)
    assert await cache.get_audio(voice_identifier, text) == b"chunk"


@pytest.mark.asyncio
async def test_safe_create_set_and_get_disabled(mocker: MockerFixture):
    from vocode.streaming.synthesizer.audio_cache import AudioCache

    # will fail the ping
    server = FakeServer()
    server.connected = False

    fake_redis = FakeAsyncRedis(server=server)

    mocker.patch(
        "vocode.streaming.synthesizer.audio_cache.initialize_redis_bytes", return_value=fake_redis
    )

    cache = await AudioCache.safe_create()
    voice_identifier = "voice_id"
    text = "text"
    audio_data = b"chunk"

    assert await cache.get_audio(voice_identifier, text) is None

    await cache.set_audio(voice_identifier, text, audio_data)

    assert await cache.get_audio(voice_identifier, text) is None
