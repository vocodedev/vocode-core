from custom_action_factory import MyCustomActionFactory
from custom_agent import CustomAgent, CustomAgentConfig

from vocode.streaming.agent.abstract_factory import AbstractAgentFactory
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import AgentConfig, ChatGPTAgentConfig


class CustomAgentFactory(AbstractAgentFactory):
    def __init__(self, agent_config: CustomAgentConfig, action_factory: MyCustomActionFactory): 
        self.agent_config = agent_config
        self.action_factory = action_factory

    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        if isinstance(agent_config, CustomAgentConfig):
            return CustomAgent(
                agent_config=self.agent_config,
                action_factory=self.action_factory
            )
        raise Exception("Invalid agent config")