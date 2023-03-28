from typing import Generator
from vocode.streaming.agent.base_agent import BaseAgent


class EchoAgent(BaseAgent):
    def respond(self, human_input, is_interrupt: bool = False) -> tuple[str, bool]:
        return human_input, False

    def generate_response(self, human_input, is_interrupt: bool = False) -> Generator:
        yield human_input

    def update_last_bot_message_on_cut_off(self, message: str):
        pass
