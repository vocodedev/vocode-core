from typing import Optional, Tuple
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.factory import AgentFactory

class SpellerAgentConfig(AgentConfig, type="agent_speller"):
    pass


class SpellerAgent(BaseAgent):
    def __init__(self, agent_config: SpellerAgentConfig):
        super().__init__(agent_config=agent_config)

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        return "".join(c + " " for c in human_input), False


class SpellerAgentFactory(AgentFactory):
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        return SpellerAgent(agent_config=agent_config)