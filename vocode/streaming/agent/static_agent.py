import logging
from .base_agent import RespondAgent
from ..models.agent import StaticAgentConfig
from vocode.streaming.models.message import BaseMessage
from typing import Optional, Tuple

class StaticAgent(RespondAgent[StaticAgentConfig]):
    def __init__(
        self,
        agent_config: StaticAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config)
        if self.agent_config.generate_responses:
            raise NotImplementedError(
                "No streamed static responses"
            )
        self.script = self.agent_config.script or []
        self.index = 0
    
    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[BaseMessage, bool]:
        response = ""
        if self.index < len(self.script):
            response = self.script[self.index]
            self.index += 1
            return BaseMessage(text=response), False
        else:
            return BaseMessage(text=""), True
