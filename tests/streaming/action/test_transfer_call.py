import asyncio
from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses
from pytest_mock import MockerFixture

from tests.fakedata.id import generate_uuid
from vocode.streaming.action.transfer_call import (
    TransferCallEmptyParameters,
    TransferCallVocodeActionConfig,
    TwilioTransferCall,
    VonageTransferCall,
)
from vocode.streaming.models.actions import (
    TwilioPhoneConversationActionInput,
    VonagePhoneConversationActionInput,
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.telephony import TwilioConfig, VonageConfig
from vocode.streaming.models.transcript import Message, Transcript
from vocode.streaming.utils import create_conversation_id
from vocode.streaming.utils.state_manager import (
    TwilioPhoneConversationStateManager,
    VonagePhoneConversationStateManager,
)

TRANSFER_PHONE_NUMBER = "12345678920"


@pytest.fixture
def mock_twilio_config():
    return TwilioConfig(
        account_sid="account_sid",
        auth_token="auth_token",
    )


@pytest.fixture
def mock_vonage_config():
    return VonageConfig(
        api_key="api_key",
        api_secret="api_secret",
        application_id="application_id",
        private_key="-----BEGIN PRIVATE KEY-----\nasdf\n-----END PRIVATE KEY-----",
    )


@pytest.fixture
def mock_twilio_phone_conversation(mock_twilio_config) -> MagicMock:
    twilio_phone_conversation = MagicMock()
    twilio_phone_conversation.twilio_config = mock_twilio_config
    return twilio_phone_conversation


@pytest.fixture
def mock_vonage_phone_conversation(mock_vonage_config) -> MagicMock:
    vonage_phone_conversation = MagicMock()
    vonage_phone_conversation.vonage_config = mock_vonage_config
    return vonage_phone_conversation


@pytest.fixture
def mock_twilio_conversation_state_manager(
    mocker: Any, mock_twilio_phone_conversation: MagicMock
) -> TwilioPhoneConversationStateManager:
    return TwilioPhoneConversationStateManager(mock_twilio_phone_conversation)


@pytest.fixture
def mock_vonage_conversation_state_manager(
    mocker: Any, mock_vonage_phone_conversation: MagicMock
) -> VonagePhoneConversationStateManager:
    return VonagePhoneConversationStateManager(mock_vonage_phone_conversation)


@pytest.mark.asyncio
async def test_twilio_transfer_call_succeeds(
    mocker: Any,
    mock_twilio_conversation_state_manager: TwilioPhoneConversationStateManager,
    mock_twilio_phone_conversation: MagicMock,
    mock_twilio_config: TwilioConfig,
):
    action = TwilioTransferCall(
        action_config=TransferCallVocodeActionConfig(phone_number=TRANSFER_PHONE_NUMBER),
    )
    user_message_tracker = asyncio.Event()
    user_message_tracker.set()
    action.attach_conversation_state_manager(mock_twilio_conversation_state_manager)
    conversation_id = create_conversation_id()

    twilio_sid = "twilio_sid"
    action_input = TwilioPhoneConversationActionInput(
        action_config=TransferCallVocodeActionConfig(phone_number=TRANSFER_PHONE_NUMBER),
        conversation_id=conversation_id,
        params=TransferCallEmptyParameters(),
        twilio_sid=twilio_sid,
        user_message_tracker=user_message_tracker,
    )

    mock_twilio_phone_conversation.transcript = Transcript(event_logs=[])

    with aioresponses() as m:
        m.post(
            "https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Calls/{twilio_call_sid}.json".format(
                twilio_account_sid=mock_twilio_config.account_sid,
                twilio_call_sid=twilio_sid,
            ),
            status=200,
        )
        action_output = await action.run(action_input=action_input)
        assert action_output.response.success, "Expected action response to be successful"
        m.assert_called_once_with(
            f"https://api.twilio.com/2010-04-01/Accounts/{mock_twilio_config.account_sid}/Calls/{twilio_sid}.json",
            method="POST",
            auth=aiohttp.BasicAuth(
                login=mock_twilio_config.account_sid,
                password=mock_twilio_config.auth_token,
            ),
            data={"Twiml": f"<Response><Dial>{TRANSFER_PHONE_NUMBER}</Dial></Response>"},
        )


@pytest.mark.asyncio
async def test_twilio_transfer_call_fails_if_interrupted(
    mocker: Any,
    mock_twilio_conversation_state_manager: TwilioPhoneConversationStateManager,
    mock_twilio_phone_conversation: MagicMock,
) -> None:
    action = TwilioTransferCall(
        action_config=TransferCallVocodeActionConfig(phone_number=TRANSFER_PHONE_NUMBER),
    )
    user_message_tracker = asyncio.Event()
    user_message_tracker.set()
    action.attach_conversation_state_manager(mock_twilio_conversation_state_manager)
    conversation_id = create_conversation_id()

    inner_transfer_call_mock = mocker.patch(
        "vocode.streaming.action.transfer_call.TwilioTransferCall.transfer_call",
        autospec=True,
    )

    mock_twilio_phone_conversation.transcript = Transcript(
        event_logs=[
            Message(
                sender=Sender.BOT,
                text="Please hold while I transfer you",
                is_end_of_turn=False,
            )
        ]
    )

    action_input = TwilioPhoneConversationActionInput(
        action_config=TransferCallVocodeActionConfig(phone_number=TRANSFER_PHONE_NUMBER),
        conversation_id=conversation_id,
        params=TransferCallEmptyParameters(),
        twilio_sid="twilio_sid",
        user_message_tracker=user_message_tracker,
    )

    action_output = await action.run(action_input=action_input)

    assert inner_transfer_call_mock.call_count == 0, "Expected transfer_call to not be called"
    assert not action_output.response.success, "Expected action response to be unsuccessful"


@pytest.mark.asyncio
async def test_vonage_transfer_call_inbound(
    mocker: MockerFixture,
    mock_env,
    mock_vonage_conversation_state_manager: VonagePhoneConversationStateManager,
) -> None:
    transfer_phone_number = "12345678920"
    action = VonageTransferCall(
        action_config=TransferCallVocodeActionConfig(phone_number=transfer_phone_number),
    )

    mocker.patch("vonage.Client._create_jwt_auth_string", return_value=b"asdf")

    vonage_uuid = generate_uuid()

    mock_vonage_conversation_state_manager._vonage_phone_conversation.direction = "inbound"
    mock_vonage_conversation_state_manager._vonage_phone_conversation.to_phone = "1234567894"
    mock_vonage_conversation_state_manager._vonage_phone_conversation.from_phone = "1234567895"

    conversation_id = create_conversation_id()

    action.attach_conversation_state_manager(mock_vonage_conversation_state_manager)

    user_message_tracker = asyncio.Event()
    user_message_tracker.set()

    with aioresponses() as m:
        m.put(
            f"https://api.nexmo.com/v1/calls/{vonage_uuid}",
            payload={},
            status=200,
        )

        action_input = VonagePhoneConversationActionInput(
            action_config=TransferCallVocodeActionConfig(phone_number=transfer_phone_number),
            conversation_id=conversation_id,
            params=TransferCallEmptyParameters(),
            vonage_uuid=str(vonage_uuid),
            user_message_tracker=user_message_tracker,
        )
        action_output = await action.run(action_input=action_input)

        assert action_output.response.success
        assert action_output.action_type == "action_transfer_call"

        call = list(m.requests.values())[0][0]

        ncco = call.kwargs["json"]["destination"]["ncco"]

        assert ncco[0]["endpoint"][0]["number"] == transfer_phone_number
        assert (
            ncco[0]["from"]
            == mock_vonage_conversation_state_manager._vonage_phone_conversation.to_phone  # if inbound, the agent number is the to_phone
        )
