import logging
import random
from typing import AsyncGenerator, Generator, Generic, Optional, Tuple, TypeVar
from vocode.streaming.models.agent import (
    AgentConfig,
    ChatGPTAgentConfig,
    LLMAgentConfig,
)

AgentConfigType = TypeVar("AgentConfigType", bound=AgentConfig)


class BaseAgent(Generic[AgentConfigType]):
    def __init__(
        self, agent_config: AgentConfigType, logger: Optional[logging.Logger] = None
    ):
        self.agent_config = agent_config

    def get_agent_config(self) -> AgentConfig:
        return self.agent_config

    def start(self):
        pass

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[Optional[str], bool]:
        raise NotImplementedError

    def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Returns a generator that yields a sentence at a time."""
        raise NotImplementedError

    def update_last_bot_message_on_cut_off(self, message: str):
        """Updates the last bot message in the conversation history when the human cuts off the bot's response."""
        pass

    def get_cut_off_response(self) -> str:
        assert isinstance(self.agent_config, LLMAgentConfig) or isinstance(
            self.agent_config, ChatGPTAgentConfig
        )
        assert self.agent_config.cut_off_response is not None
        on_cut_off_messages = self.agent_config.cut_off_response.messages
        assert len(on_cut_off_messages) > 0
        return random.choice(on_cut_off_messages).text

    def terminate(self):
        pass
