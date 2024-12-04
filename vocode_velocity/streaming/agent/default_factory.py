from vocode.streaming.agent.abstract_factory import AbstractAgentFactory
from vocode.streaming.agent.anthropic_agent import AnthropicAgent
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.agent.restful_user_implemented_agent import RESTfulUserImplementedAgent
from vocode.streaming.models.agent import (
    AgentConfig,
    AnthropicAgentConfig,
    ChatGPTAgentConfig,
    EchoAgentConfig,
    RESTfulUserImplementedAgentConfig,
)


class DefaultAgentFactory(AbstractAgentFactory):
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        if isinstance(agent_config, ChatGPTAgentConfig):
            return ChatGPTAgent(agent_config=agent_config)
        elif isinstance(agent_config, EchoAgentConfig):
            return EchoAgent(agent_config=agent_config)
        elif isinstance(agent_config, RESTfulUserImplementedAgentConfig):
            return RESTfulUserImplementedAgent(agent_config=agent_config)
        elif isinstance(agent_config, AnthropicAgentConfig):
            return AnthropicAgent(agent_config=agent_config)
        raise Exception("Invalid agent config", agent_config.type)
