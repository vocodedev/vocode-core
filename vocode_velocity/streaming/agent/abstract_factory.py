from abc import ABC, abstractmethod

from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.agent import AgentConfig


class AbstractAgentFactory(ABC):
    @abstractmethod
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        pass
