import asyncio
from typing import Generator, Type
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic.v1 import BaseModel
from pytest_mock import MockerFixture

from tests.fakedata.id import generate_uuid
from vocode.streaming.action.end_conversation import (
    EndConversation,
    EndConversationParameters,
    EndConversationVocodeActionConfig,
)
from vocode.streaming.models.actions import (
    TwilioPhoneConversationActionInput,
    VonagePhoneConversationActionInput,
)
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.utils import create_conversation_id


class EndConversationActionTestCase(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    action: EndConversation
    vonage_uuid: UUID
    twilio_sid: str
    conversation_id: str


@pytest.fixture
def end_conversation_action_test_case(mocker: MockerFixture) -> EndConversationActionTestCase:
    action = EndConversation(action_config=EndConversationVocodeActionConfig())
    return EndConversationActionTestCase(
        action=action,
        vonage_uuid=generate_uuid(),
        twilio_sid="twilio_sid",
        conversation_id=create_conversation_id(),
    )


@pytest.fixture
def conversation_state_manager_mock(mocker: MockerFixture) -> MagicMock:
    mock = mocker.MagicMock()
    mock.terminate_conversation = mocker.AsyncMock()
    mock.transcript = Transcript()
    return mock


@pytest.fixture
def user_message_tracker() -> asyncio.Event:
    tracker = asyncio.Event()
    tracker.set()
    return tracker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_input_class, identifier",
    [
        (VonagePhoneConversationActionInput, "vonage_uuid"),
        (TwilioPhoneConversationActionInput, "twilio_sid"),
    ],
)
async def test_end_conversation_success(
    mocker: MockerFixture,
    mock_env: Generator,
    end_conversation_action_test_case: EndConversationActionTestCase,
    conversation_state_manager_mock: MagicMock,
    user_message_tracker: asyncio.Event,
    action_input_class: Type[BaseModel],
    identifier: str,
):
    end_conversation_action_test_case.action.attach_conversation_state_manager(
        conversation_state_manager_mock
    )

    identifier_value = getattr(end_conversation_action_test_case, identifier)
    action_input = action_input_class(
        action_config=EndConversationVocodeActionConfig(),
        conversation_id=end_conversation_action_test_case.conversation_id,
        params=EndConversationParameters(),
        **{identifier: str(identifier_value)},
        user_message_tracker=user_message_tracker,
    )

    response = await end_conversation_action_test_case.action.run(action_input=action_input)

    assert response.response.success
    assert conversation_state_manager_mock.terminate_conversation.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_input_class, identifier",
    [
        (VonagePhoneConversationActionInput, "vonage_uuid"),
        (TwilioPhoneConversationActionInput, "twilio_sid"),
    ],
)
async def test_end_conversation_fails_if_interrupted(
    mocker: MockerFixture,
    mock_env: Generator,
    end_conversation_action_test_case: EndConversationActionTestCase,
    conversation_state_manager_mock: MagicMock,
    user_message_tracker: asyncio.Event,
    action_input_class: Type[BaseModel],
    identifier: str,
):
    conversation_state_manager_mock.transcript.add_bot_message(
        "Unfinished", conversation_id=end_conversation_action_test_case.conversation_id
    )
    end_conversation_action_test_case.action.attach_conversation_state_manager(
        conversation_state_manager_mock
    )

    identifier_value = getattr(end_conversation_action_test_case, identifier)
    action_input = action_input_class(
        action_config=EndConversationVocodeActionConfig(),
        conversation_id=end_conversation_action_test_case.conversation_id,
        params=EndConversationParameters(),
        **{identifier: str(identifier_value)},
        user_message_tracker=user_message_tracker,
    )

    response = await end_conversation_action_test_case.action.run(action_input=action_input)

    assert not response.response.success
    assert conversation_state_manager_mock.terminate_conversation.call_count == 0
