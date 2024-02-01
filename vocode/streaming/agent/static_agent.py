import logging
from .base_agent import RespondAgent
from ..models.agent import StaticAgentConfig
from vocode.streaming.models.message import BaseMessage
from typing import Optional, Tuple, AsyncGenerator

class StaticAgent(RespondAgent[StaticAgentConfig]):
    def __init__(
        self,
        agent_config: StaticAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config)
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

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[BaseMessage, None]:
        if self.index < len(self.script):
            response = BaseMessage(text=self.script[self.index])
            self.index += 1
            if self.index == len(self.script):
                response.metadata["stop"] = True
            yield response
        else:
            yield BaseMessage(text="", metadata={"stop": True})
