from typing import AsyncGenerator, Generator, Optional, Tuple
from vocode.streaming.agent.base_agent import BaseAgent, RespondAgent
from vocode.streaming.models.agent import EchoAgentConfig
from vocode.streaming.models.message import BaseMessage


class EchoAgent(RespondAgent[EchoAgentConfig]):
    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[BaseMessage, bool]:
        return BaseMessage(text=human_input), False

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[BaseMessage, None]:
        yield BaseMessage(text=human_input)

    def update_last_bot_message_on_cut_off(self, message: str):
        pass
