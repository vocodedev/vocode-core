from __future__ import annotations

import asyncio
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import ActionResultAgentInput, AgentInput
from vocode.streaming.models.actions import (
    ActionInput,
    TwilioPhoneCallActionInput,
    VonagePhoneCallActionInput,
)
from vocode.streaming.utils.state_manager import ConversationStateManager
from vocode.streaming.utils.worker import (
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleWorker,
)


class ActionsWorker(InterruptibleWorker):
    def __init__(
        self,
        input_queue: asyncio.Queue[InterruptibleEvent[ActionInput]],
        output_queue: asyncio.Queue[InterruptibleEvent[AgentInput]],
        interruptible_event_factory: InterruptibleEventFactory = InterruptibleEventFactory(),
        action_factory: ActionFactory = ActionFactory(),
    ):
        super().__init__(
            input_queue=input_queue,
            output_queue=output_queue,
            interruptible_event_factory=interruptible_event_factory,
        )
        self.action_factory = action_factory

    def attach_conversation_state_manager(
        self, conversation_state_manager: ConversationStateManager
    ):
        self.conversation_state_manager = conversation_state_manager

    async def process(self, item: InterruptibleEvent[ActionInput]):
        action_input = item.payload
        action = self.action_factory.create_action(action_input.action_config)
        action.attach_conversation_state_manager(self.conversation_state_manager)

        # Run the action in the background
        asyncio.create_task(self._run_action_and_produce_event(action, action_input))

    async def _run_action_and_produce_event(self, action, action_input):
        action_output = await action.run(action_input)
        self.produce_interruptible_agent_response_event_nonblocking(
            ActionResultAgentInput(
                conversation_id=action_input.conversation_id,
                action_input=action_input,
                action_output=action_output,
                vonage_uuid=(
                    action_input.vonage_uuid
                    if isinstance(action_input, VonagePhoneCallActionInput)
                    else None
                ),
                twilio_sid=(
                    action_input.twilio_sid
                    if isinstance(action_input, TwilioPhoneCallActionInput)
                    else None
                ),
                is_quiet=action.quiet,
            )
        )
