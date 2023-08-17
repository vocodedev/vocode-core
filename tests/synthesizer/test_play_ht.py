import asyncio

from aioresponses import aioresponses
from pydub import AudioSegment
import pytest

from vocode.streaming.models.message import BaseMessage
from vocode.streaming.synthesizer.base_synthesizer import SynthesisResult
from vocode.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer


async def assert_synthesis_result_valid(synthesizer: PlayHtSynthesizer):
    response = await synthesizer.create_speech(BaseMessage(text="Hello, world!"), 1024)
    assert isinstance(response, SynthesisResult)
    assert response.chunk_generator is not None
    audio = AudioSegment.empty()
    async for chunk in response.chunk_generator:
        audio += AudioSegment(
            chunk.chunk,
            frame_rate=synthesizer.synthesizer_config.sampling_rate,
            sample_width=2,
            channels=1,
        )


@pytest.mark.asyncio
async def test_with_api_key(
    fixture_play_ht_synthesizer_with_api_key: PlayHtSynthesizer,
    mock_play_ht_api: aioresponses,
):
    await assert_synthesis_result_valid(await fixture_play_ht_synthesizer_with_api_key)


@pytest.mark.asyncio
async def test_with_wrong_api_key(
    fixture_play_ht_synthesizer_wrong_api_key: PlayHtSynthesizer,
    mock_play_ht_api: aioresponses,
):
    with pytest.raises(Exception, match="Play.ht API error status code 401"):
        await (await fixture_play_ht_synthesizer_wrong_api_key).create_speech(
            BaseMessage(text="Hello, world!"), 1024
        )

@pytest.mark.asyncio
async def test_with_wrong_user_id(
    fixture_play_ht_synthesizer_wrong_user_id: PlayHtSynthesizer,
    mock_play_ht_api: aioresponses,
):
    with pytest.raises(Exception, match="Play.ht API error status code 401"):
        await (await fixture_play_ht_synthesizer_wrong_user_id).create_speech(
            BaseMessage(text="Hello, world!"), 1024
        )



@pytest.mark.asyncio
async def test_with_env_api_key(
    fixture_play_ht_synthesizer_env_api_key: PlayHtSynthesizer,
    mock_play_ht_api: aioresponses,
):
    await assert_synthesis_result_valid(await fixture_play_ht_synthesizer_env_api_key)
