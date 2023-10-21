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
    InterruptableEvent,
    InterruptableEventFactory,
    InterruptableWorker,
)


class ActionsWorker(InterruptableWorker):
    def __init__(
        self,
        input_queue: asyncio.Queue[InterruptableEvent[ActionInput]],
        output_queue: asyncio.Queue[InterruptableEvent[AgentInput]],
        interruptable_event_factory: InterruptableEventFactory = InterruptableEventFactory(),
        action_factory: ActionFactory = ActionFactory(),
    ):
        super().__init__(
            input_queue=input_queue,
            output_queue=output_queue,
            interruptable_event_factory=interruptable_event_factory,
        )
        self.action_factory = action_factory

    def attach_conversation_state_manager(
        self, conversation_state_manager: ConversationStateManager
    ):
        self.conversation_state_manager = conversation_state_manager

    async def process(self, item: InterruptableEvent[ActionInput]):
        action_input = item.payload
        action = self.action_factory.create_action(action_input.action_config)
        action.attach_conversation_state_manager(self.conversation_state_manager)
        action_output = await action.run(action_input)
        self.produce_interruptable_event_nonblocking(
            ActionResultAgentInput(
                conversation_id=action_input.conversation_id,
                action_input=action_input,
                action_output=action_output,
                vonage_uuid=action_input.vonage_uuid
                if isinstance(action_input, VonagePhoneCallActionInput)
                else None,
                twilio_sid=action_input.twilio_sid
                if isinstance(action_input, TwilioPhoneCallActionInput)
                else None,
                is_quiet=action.quiet,
            )
        )
