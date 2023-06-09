from __future__ import annotations

import asyncio
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import ActionResultAgentInput, AgentInput
from vocode.streaming.models.actions import ActionInput, ActionOutput
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

    async def process(self, item: InterruptibleEvent[ActionInput]):
        action_input = item.payload
        action = self.action_factory.create_action(action_input.action_type)
        action_output = action.run(action_input.params)
        self.produce_interruptible_event_nonblocking(
            ActionResultAgentInput(
                conversation_id=action_input.conversation_id,
                action_output=action_output,
            )
        )
