import pytest
from aioresponses import aioresponses
from tests.fakedata.id import generate_uuid

from vocode.streaming.action.dtmf import (
    DTMFParameters,
    DTMFVocodeActionConfig,
    TwilioDTMF,
    VonageDTMF,
)
from vocode.streaming.models.actions import (
    TwilioPhoneConversationActionInput,
    VonagePhoneConversationActionInput,
)
from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.utils import create_conversation_id
from vocode.streaming.utils.state_manager import VonagePhoneConversationStateManager


@pytest.mark.asyncio
async def test_vonage_dtmf_press_digits(mocker, mock_env):
    action = VonageDTMF(action_config=DTMFVocodeActionConfig())
    vonage_uuid = generate_uuid()
    digits = "1234"

    vonage_phone_conversation_mock = mocker.MagicMock()
    vonage_config = VonageConfig(
        api_key="api_key",
        api_secret="api_secret",
        application_id="application_id",
        private_key="-----BEGIN PRIVATE KEY-----\nasdf\n-----END PRIVATE KEY-----",
    )
    vonage_phone_conversation_mock.vonage_config = vonage_config
    mocker.patch("vonage.Client._create_jwt_auth_string", return_value=b"asdf")

    action.attach_conversation_state_manager(
        VonagePhoneConversationStateManager(vonage_phone_conversation_mock)
    )

    assert (
        action.conversation_state_manager.create_vonage_client().get_telephony_config()
        == vonage_config
    )

    with aioresponses() as m:
        m.put(
            f"https://api.nexmo.com/v1/calls/{vonage_uuid}/dtmf",
            status=200,
        )
        action_output = await action.run(
            action_input=VonagePhoneConversationActionInput(
                action_config=DTMFVocodeActionConfig(),
                conversation_id=create_conversation_id(),
                params=DTMFParameters(buttons=digits),
                vonage_uuid=str(vonage_uuid),
            )
        )

        assert action_output.response.success is True


@pytest.mark.asyncio
async def test_twilio_dtmf_press_digits(mocker, mock_env):
    action = TwilioDTMF(action_config=DTMFVocodeActionConfig())
    digits = "1234"
    twilio_sid = "twilio_sid"

    action_output = await action.run(
        action_input=TwilioPhoneConversationActionInput(
            action_config=DTMFVocodeActionConfig(),
            conversation_id=create_conversation_id(),
            params=DTMFParameters(buttons=digits),
            twilio_sid=twilio_sid,
        )
    )

    assert action_output.response.success is False  # Twilio does not support DTMF
