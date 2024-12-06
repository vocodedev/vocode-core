from abc import ABC, abstractmethod

from svara.streaming.agent.base_agent import BaseAgent
from svara.streaming.models.agent import AgentConfig


class AbstractAgentFactory(ABC):
    @abstractmethod
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        pass
