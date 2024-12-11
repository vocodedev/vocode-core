from typing import AsyncGenerator, Tuple
from vocode.streaming.agent.base_agent import RespondAgent
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
    ) -> AsyncGenerator[Tuple[str, bool], None]:
        yield human_input, True

    def update_last_bot_message_on_cut_off(self, message: str):
        pass

    def cancel_stream(self):  # stub to try fix streaming conversation for echo agent
        pass
