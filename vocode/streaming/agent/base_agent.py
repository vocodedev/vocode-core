import logging
import random
from typing import Generator, Optional, Tuple
from vocode.streaming.models.agent import (
    AgentConfig,
    ChatGPTAgentConfig,
    LLMAgentConfig,
)


class BaseAgent:
    def __init__(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ):
        self.agent_config = agent_config

    def get_agent_config(self) -> AgentConfig:
        return self.agent_config

    def start(self):
        pass

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        raise NotImplementedError

    def generate_response(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Returns a generator that yields a sentence at a time."""
        raise NotImplementedError

    def update_last_bot_message_on_cut_off(self, message: str):
        """Updates the last bot message in the conversation history when the human cuts off the bot's response."""
        pass

    def get_cut_off_response(self) -> Optional[str]:
        assert isinstance(self.agent_config, LLMAgentConfig) or isinstance(
            self.agent_config, ChatGPTAgentConfig
        )
        on_cut_off_messages = self.agent_config.cut_off_response.messages
        if on_cut_off_messages:
            return random.choice(on_cut_off_messages).text

    def terminate(self):
        pass
