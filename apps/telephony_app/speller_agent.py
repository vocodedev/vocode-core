import logging
from typing import Optional, Tuple
import typing
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import AgentConfig, AgentType, ChatGPTAgentConfig
from vocode.streaming.agent.base_agent import BaseAgent, RespondAgent
from vocode.streaming.agent.factory import AgentFactory


class SpellerAgentConfig(AgentConfig, type="agent_speller"):
    pass


class SpellerAgent(RespondAgent[SpellerAgentConfig]):
    def __init__(self, agent_config: SpellerAgentConfig):
        super().__init__(agent_config=agent_config)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[Optional[str], bool]:
        return "".join(c + " " for c in human_input), False


class SpellerAgentFactory(AgentFactory):
    def create_agent(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ) -> BaseAgent:
        if agent_config.type == AgentType.CHAT_GPT:
            return ChatGPTAgent(
                agent_config=typing.cast(ChatGPTAgentConfig, agent_config)
            )
        elif agent_config.type == "agent_speller":
            return SpellerAgent(
                agent_config=typing.cast(SpellerAgentConfig, agent_config)
            )
        raise Exception("Invalid agent config")
