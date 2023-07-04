from typing import AsyncGenerator, Generator, Optional, Tuple
from vocode.streaming.agent.base_agent import BaseAgent, RespondAgent
from vocode.streaming.models.agent import EchoAgentConfig


class EchoAgent(RespondAgent[EchoAgentConfig]):
    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        return human_input, False

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        yield human_input

    def update_last_bot_message_on_cut_off(self, message: str):
        pass
