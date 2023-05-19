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
from vocode.streaming.models.agent import (
    AgentConfig,
    AgentType,
    ChatAnthropicAgentConfig,
    ChatGPTAgentConfig,
    EchoAgentConfig,
    InformationRetrievalAgentConfig,
    LLMAgentConfig,
    RESTfulUserImplementedAgentConfig,
)


class AgentFactory:
    def create_agent(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ) -> BaseAgent:
        if agent_config.type == AgentType.LLM:
            return LLMAgent(
                agent_config=typing.cast(LLMAgentConfig, agent_config), logger=logger
            )
        elif agent_config.type == AgentType.CHAT_GPT:
            return ChatGPTAgent(
                agent_config=typing.cast(ChatGPTAgentConfig, agent_config),
                logger=logger,
            )
        elif agent_config.type == AgentType.ECHO:
            return EchoAgent(
                agent_config=typing.cast(EchoAgentConfig, agent_config), logger=logger
            )
        elif agent_config.type == AgentType.INFORMATION_RETRIEVAL:
            return InformationRetrievalAgent(
                agent_config=typing.cast(InformationRetrievalAgentConfig, agent_config),
                logger=logger,
            )
        elif agent_config.type == AgentType.RESTFUL_USER_IMPLEMENTED:
            return RESTfulUserImplementedAgent(
                agent_config=typing.cast(
                    RESTfulUserImplementedAgentConfig, agent_config
                ),
                logger=logger,
            )
        elif agent_config.type == AgentType.CHAT_ANTHROPIC:
            return ChatAnthropicAgent(
                agent_config=typing.cast(ChatAnthropicAgentConfig, agent_config),
                logger=logger,
            )
        raise Exception("Invalid agent config", agent_config.type)
