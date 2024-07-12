from typing import AsyncGenerator, Literal

from vocode.streaming.agent.abstract_factory import AbstractAgentFactory
from vocode.streaming.agent.base_agent import BaseAgent, GeneratedResponse, RespondAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import AgentConfig, ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage


class SpellerAgentConfig(AgentConfig):
    """Configuration for SpellerAgent. Inherits from AgentConfig."""

    type: Literal["agent_speller"] = "agent_speller"


class SpellerAgent(RespondAgent[SpellerAgentConfig]):
    """SpellerAgent class. Inherits from RespondAgent.

    This agent takes human input and returns it with spaces between each character.
    """

    def __init__(self, agent_config: SpellerAgentConfig):
        """Initializes SpellerAgent with the given configuration.

        Args:
            agent_config (SpellerAgentConfig): The configuration for this agent.
        """
        super().__init__(agent_config=agent_config)

    def _spell(self, text: str) -> str:
        """Returns the given text with spaces between each character.

        Args:
            text (str): The text to be spelled.

        Returns:
            str: The text with spaces between each character.
        """
        return "".join(c + " " for c in text)

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
        bot_was_in_medias_res: bool = False,
    ) -> AsyncGenerator[GeneratedResponse, None]:
        yield GeneratedResponse(
            message=BaseMessage(text=self._spell(human_input)), is_interruptible=True
        )


class SpellerAgentFactory(AbstractAgentFactory):
    """Factory class for creating agents based on the provided agent configuration."""

    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """Creates an agent based on the provided agent configuration.

        Args:
            agent_config (AgentConfig): The configuration for the agent to be created.

        Returns:
            BaseAgent: The created agent.

        Raises:
            Exception: If the agent configuration type is not recognized.
        """
        # If the agent configuration type is CHAT_GPT, create a ChatGPTAgent.
        if isinstance(agent_config, ChatGPTAgentConfig):
            return ChatGPTAgent(agent_config=agent_config)
        # If the agent configuration type is agent_speller, create a SpellerAgent.
        elif isinstance(agent_config, SpellerAgentConfig):
            return SpellerAgent(agent_config=agent_config)
        # If the agent configuration type is not recognized, raise an exception.
        raise Exception("Invalid agent config")
