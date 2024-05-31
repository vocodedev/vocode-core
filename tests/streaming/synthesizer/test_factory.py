from unittest.mock import MagicMock, patch

from pyht import AsyncClient
from pyht.client import CongestionCtrl
from pytest_mock import MockerFixture

from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig
from vocode.streaming.synthesizer.default_factory import DefaultSynthesizerFactory

DEFAULT_PARAMS = {
    "sampling_rate": 16000,
    "audio_encoding": AudioEncoding.LINEAR16,
    "voice_id": "s3://manifest.json",
}


def test_get_play_ht_synthesizer_v2_or_v1(mocker: MockerFixture):
    factory = DefaultSynthesizerFactory()

    v1_constructor = mocker.patch("vocode.streaming.synthesizer.default_factory.PlayHtSynthesizer")
    v2_constructor = mocker.patch(
        "vocode.streaming.synthesizer.default_factory.PlayHtSynthesizerV2"
    )

    factory.create_synthesizer(
        PlayHtSynthesizerConfig(version="2", **DEFAULT_PARAMS.copy()),
    ),
    v2_constructor.assert_called_once()
    v2_constructor.reset_mock()

    factory.create_synthesizer(
        PlayHtSynthesizerConfig(version="1", **DEFAULT_PARAMS.copy()),
    )
    v1_constructor.assert_called_once()
    v1_constructor.reset_mock()

    factory.create_synthesizer(
        PlayHtSynthesizerConfig(**DEFAULT_PARAMS.copy()),
    )
    v2_constructor.assert_called_once()


def test_create_play_ht_synthesizer_on_prem(mocker: MockerFixture):
    with patch(
        "vocode.streaming.synthesizer.play_ht_synthesizer_v2.AsyncClient",
        new_callable=MagicMock,
    ) as MockOSClient:
        MockOSClient.AdvancedOptions = AsyncClient.AdvancedOptions

        user_id = "user_id"
        api_key = "api_key"
        factory = DefaultSynthesizerFactory()

        factory.create_synthesizer(
            PlayHtSynthesizerConfig(
                version="2", **DEFAULT_PARAMS.copy(), user_id=user_id, api_key=api_key
            ),
        )

        MockOSClient.assert_called_once_with(user_id=user_id, api_key=api_key)

        MockOSClient.reset_mock()

        factory.create_synthesizer(
            PlayHtSynthesizerConfig(
                version="2",
                on_prem=True,
                on_prem_provider="aws",
                **DEFAULT_PARAMS.copy(),
                user_id=user_id,
                api_key=api_key
            ),
        )

        advanced_options = AsyncClient.AdvancedOptions(
            grpc_addr=None,
            fallback_enabled=True,
            congestion_ctrl=CongestionCtrl.STATIC_MAR_2023,
        )

        MockOSClient.assert_called_with(
            user_id=user_id,
            api_key=api_key,
            advanced=advanced_options,
        )
        MockOSClient.reset_mock()
