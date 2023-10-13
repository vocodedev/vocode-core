import logging
from typing import Optional
import typing
from vocode.streaming.agent.anthropic_agent import ChatAnthropicAgent
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.agent.information_retrieval_agent import InformationRetrievalAgent
from vocode.streaming.agent.llm_agent import LLMAgent
from vocode.streaming.agent.restful_user_implemented_agent import (
    RESTfulUserImplementedAgent,
)
from vocode.streaming.agent.llamacpp_agent import LlamacppAgent
from vocode.streaming.models.agent import (
    AgentConfig,
    AgentType,
    ChatAnthropicAgentConfig,
    ChatGPTAgentConfig,
    EchoAgentConfig,
    InformationRetrievalAgentConfig,
    LLMAgentConfig,
    RESTfulUserImplementedAgentConfig,
    LlamacppAgentConfig
)


class AgentFactory:
    def create_agent(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ) -> BaseAgent:
        if isinstance(agent_config, LLMAgentConfig):
            return LLMAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, ChatGPTAgentConfig):
            return ChatGPTAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, EchoAgentConfig):
            return EchoAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, InformationRetrievalAgentConfig):
            return InformationRetrievalAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, RESTfulUserImplementedAgentConfig):
            return RESTfulUserImplementedAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, ChatAnthropicAgentConfig):
            return ChatAnthropicAgent(agent_config=agent_config, logger=logger)
        elif isinstance(agent_config, LlamacppAgentConfig):
            return LlamacppAgent(agent_config=agent_config, logger=logger)
        raise Exception("Invalid agent config", agent_config.type)
