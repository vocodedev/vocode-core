import asyncio
import base64
import io
import json
import wave

import pytest
from aiohttp import web
from pydantic.v1 import ValidationError

from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SixtyDBSynthesizerConfig, SynthesizerConfig
from vocode.streaming.synthesizer.default_factory import DefaultSynthesizerFactory
from vocode.streaming.synthesizer.sixty_db_synthesizer import (
    SixtyDBError,
    SixtyDBSynthesizer,
    decode_audio,
)
from vocode.streaming.utils import convert_linear_audio
from vocode.streaming.utils.async_requester import AsyncRequestor

PCM = b"\x10\x00\xf0\xff" * 240


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(PCM)
    return output.getvalue()


@pytest.mark.parametrize(
    "data,mime",
    [
        (PCM, "audio/pcm"),
        (wav_bytes(), "audio/wav"),
        (json.dumps({"audio_base64": base64.b64encode(PCM).decode()}).encode(), "application/json"),
        (
            (
                json.dumps({"result": {"audioContent": base64.b64encode(PCM[:101]).decode()}})
                + "\n"
                + json.dumps({"result": {"audioContent": base64.b64encode(PCM[101:]).decode()}})
            ).encode(),
            "application/x-ndjson",
        ),
        (
            json.dumps(
                {
                    "result": {
                        "audioContent": base64.b64encode(
                            json.dumps(
                                {
                                    "audio_base64": base64.b64encode(PCM).decode(),
                                    "sample_rate": 24000,
                                }
                            ).encode()
                        ).decode()
                    }
                }
            ).encode(),
            "application/json",
        ),
    ],
)
def test_audio_envelopes(data, mime):
    assert decode_audio(data, mime) == (PCM, 24000)


@pytest.mark.parametrize(
    "data,mime",
    [
        (b"", "audio/pcm"),
        (b"x", "audio/pcm"),
        (b"ID3bad", "application/octet-stream"),
        (PCM, "audio/mpeg"),
        (b"{}", "application/json"),
        (b'{"audio_base64":"!!!"}', "application/json"),
        (b'{"success":false}', "application/json"),
        (wav_bytes()[:-2], "audio/wav"),
        (b'{"sample_rate":0,"audio_base64":"AAAA"}', "application/json"),
    ],
)
def test_rejects_invalid_audio(data, mime):
    with pytest.raises(SixtyDBError):
        decode_audio(data, mime)


def test_config_registration_validation_and_cache_identity():
    config = SixtyDBSynthesizerConfig.from_telephone_output_device(
        voice_id="workspace-voice", api_key="secret"
    )
    assert isinstance(SynthesizerConfig.parse_obj(config.dict()), SixtyDBSynthesizerConfig)
    identifier = SixtyDBSynthesizer.get_voice_identifier(config)
    assert "secret" not in identifier
    assert identifier != SixtyDBSynthesizer.get_voice_identifier(
        config.copy(update={"api_key": "other"})
    )
    for changes in (
        {"voice_id": " "},
        {"speed": 3},
        {"sampling_rate": 16000},
        {"should_encode_as_wav": True},
    ):
        with pytest.raises(ValidationError):
            SixtyDBSynthesizerConfig(**{**config.dict(), **changes})


@pytest.mark.asyncio
async def test_http_synthesis_conversion_errors_and_cancellation():
    requests = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request):
        body = await request.json()
        requests.append((request.headers.get("Authorization"), body))
        if body["text"] == "error":
            return web.Response(status=401, text="sensitive server detail")
        if body["text"] == "cancel":
            response = web.StreamResponse(headers={"Content-Type": "audio/pcm"})
            await response.prepare(request)
            started.set()
            await release.wait()
            return response
        return web.Response(body=PCM, content_type="audio/pcm")

    app = web.Application()
    app.router.add_post("/tts", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    config = SixtyDBSynthesizerConfig.from_telephone_output_device(
        voice_id="workspace-voice", api_key="secret", base_url=f"http://127.0.0.1:{port}/tts"
    )
    # Earlier synchronous factory tests may leave a session bound to a closed loop.
    await AsyncRequestor().close_session()
    synth = DefaultSynthesizerFactory().create_synthesizer(config)
    assert isinstance(synth, SixtyDBSynthesizer)
    try:
        result = await synth.create_speech_uncached(BaseMessage(text="hello"), 80)
        chunks = [chunk async for chunk in result.chunk_generator]
        expected = convert_linear_audio(PCM, 24000, 8000, AudioEncoding.MULAW)
        actual = b"".join(chunk.chunk for chunk in chunks)
        assert actual[: len(expected)] == expected
        assert actual[len(expected) :] == b"\xff" * (len(actual) - len(expected))
        assert all(len(chunk.chunk) == 80 for chunk in chunks)
        assert [chunk.is_last_chunk for chunk in chunks] == [False] * (len(chunks) - 1) + [True]
        assert result.get_message_up_to(None) == "hello"
        assert result.get_message_up_to(0) == ""
        linear = DefaultSynthesizerFactory().create_synthesizer(
            config.copy(
                update={
                    "audio_encoding": AudioEncoding.LINEAR16,
                    "sampling_rate": 24000,
                    "should_encode_as_wav": True,
                }
            )
        )
        wav_result = await linear.create_speech_uncached(BaseMessage(text="wav"), 240)
        wav_chunks = [chunk async for chunk in wav_result.chunk_generator]
        decoded = []
        for chunk in wav_chunks:
            with wave.open(io.BytesIO(chunk.chunk), "rb") as audio:
                assert audio.getframerate() == 24000
                assert audio.getsampwidth() == 2
                decoded.append(audio.readframes(audio.getnframes()))
        assert b"".join(decoded) == PCM
        assert wav_chunks[-1].is_last_chunk
        for text, size in ((" ", 80), ("x" * 5001, 80), ("hello", 0)):
            with pytest.raises(ValueError):
                await synth.create_speech_uncached(BaseMessage(text=text), size)
        auth, body = requests[0]
        assert auth == "Bearer secret"
        assert body["voice_id"] == "workspace-voice"
        assert body["audio_config"] == {"audio_encoding": "LINEAR16", "sample_rate_hertz": 24000}
        with pytest.raises(SixtyDBError, match=r"\(401\)") as error:
            await synth.create_speech_uncached(BaseMessage(text="error"), 80)
        assert "sensitive" not in str(error.value)
        task = asyncio.create_task(synth.create_speech_uncached(BaseMessage(text="cancel"), 80))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        # The shared session remains usable after cancellation.
        await synth.create_speech_uncached(BaseMessage(text="again"), 80)
    finally:
        release.set()
        await synth.async_requestor.close_session()
        await synth.async_requestor.close_client()
        await runner.cleanup()
