from abc import ABC, abstractmethod

from vocode_velocity.streaming.agent.base_agent import BaseAgent
from vocode_velocity.streaming.models.agent import AgentConfig


class AbstractAgentFactory(ABC):
    @abstractmethod
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        pass
