import pytest

from vocode.streaming.action.wait import Wait, WaitParameters, WaitVocodeActionConfig
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.utils import create_conversation_id


@pytest.mark.asyncio
async def test_wait_action_success_without_user_message_tracker():
    action_config = WaitVocodeActionConfig()
    wait_action = Wait(action_config=action_config)
    action_input = ActionInput[WaitParameters](
        action_config=action_config,
        conversation_id=create_conversation_id(),
        user_message_tracker=None,
        params=WaitParameters(),
    )

    action_output = await wait_action.run(action_input)

    assert (
        action_output.response.success is True
    ), "Expected the wait action to succeed without a user message tracker"
