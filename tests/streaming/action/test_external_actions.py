import base64
import json
import os

import pytest

from tests.fakedata.id import generate_uuid
from vocode.streaming.action.execute_external_action import (
    ExecuteExternalAction,
    ExecuteExternalActionParameters,
    ExecuteExternalActionVocodeActionConfig,
)
from vocode.streaming.action.external_actions_requester import ExternalActionResponse
from vocode.streaming.models.actions import (
    TwilioPhoneConversationActionInput,
    VonagePhoneConversationActionInput,
)
from vocode.streaming.utils import create_conversation_id
from vocode.streaming.utils.state_manager import (
    TwilioPhoneConversationStateManager,
    VonagePhoneConversationStateManager,
)

ACTION_INPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "length": {"type": "string", "enum": ["30m", "1hr"]},
        "time": {"type": "string", "pattern": r"^\d{2}:\d0[ap]m$"},
    },
}


@pytest.fixture
def action_config() -> dict:
    """Provides a common action configuration for tests."""
    return {
        "processing_mode": "muted",
        "name": "name",
        "description": "A description",
        "url": "https://example.com",
        "input_schema": json.dumps(ACTION_INPUT_SCHEMA),
        "speak_on_send": True,
        "speak_on_receive": True,
        "signature_secret": base64.b64encode(os.urandom(32)).decode(),
    }


@pytest.fixture
def execute_action_setup(mocker, action_config) -> ExecuteExternalAction:
    """Common setup for creating an ExecuteExternalAction instance."""
    action = ExecuteExternalAction(
        action_config=ExecuteExternalActionVocodeActionConfig(**action_config),
    )
    mocked_requester = mocker.AsyncMock()
    mocked_requester.send_request.return_value = ExternalActionResponse(
        result={"test": "test"},
        agent_message="message!",
        success=True,
    )
    action.external_actions_requester = mocked_requester
    return action


@pytest.fixture
def mock_twilio_conversation_state_manager(mocker) -> TwilioPhoneConversationStateManager:
    """Fixture to mock TwilioPhoneConversationStateManager."""
    manager = mocker.MagicMock(spec=TwilioPhoneConversationStateManager)
    manager.mute_agent = mocker.MagicMock()
    # Add any other necessary mock setup here
    return manager


@pytest.fixture
def mock_vonage_conversation_state_manager(mocker) -> VonagePhoneConversationStateManager:
    """Fixture to mock VonagePhoneConversationStateManager."""
    manager = mocker.MagicMock(spec=VonagePhoneConversationStateManager)
    manager.mute_agent = mocker.MagicMock()
    # Add any other necessary mock setup here
    return manager


@pytest.mark.asyncio
async def test_vonage_execute_external_action_success(
    mocker,
    mock_vonage_conversation_state_manager: VonagePhoneConversationStateManager,
    execute_action_setup: ExecuteExternalAction,
):
    execute_action_setup.attach_conversation_state_manager(mock_vonage_conversation_state_manager)
    vonage_uuid = generate_uuid()

    response = await execute_action_setup.run(
        action_input=VonagePhoneConversationActionInput(
            action_config=execute_action_setup.action_config,
            conversation_id=create_conversation_id(),
            params=ExecuteExternalActionParameters(payload={}),
            vonage_uuid=str(vonage_uuid),
        ),
    )

    assert response.response.success
    assert response.response.result == {"test": "test"}


@pytest.mark.asyncio
async def test_twilio_execute_external_action_success(
    mocker,
    mock_twilio_conversation_state_manager: TwilioPhoneConversationStateManager,
    execute_action_setup: ExecuteExternalAction,
):
    execute_action_setup.attach_conversation_state_manager(mock_twilio_conversation_state_manager)

    response = await execute_action_setup.run(
        action_input=TwilioPhoneConversationActionInput(
            action_config=execute_action_setup.action_config,
            conversation_id=create_conversation_id(),
            params=ExecuteExternalActionParameters(payload={}),
            twilio_sid="twilio_sid",
        ),
    )

    assert response.response.success
    assert response.response.result == {"test": "test"}
