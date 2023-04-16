from .base_agent import BaseAgent
from ..models.agent import (
    RESTfulUserImplementedAgentConfig,
    RESTfulAgentInput,
    RESTfulAgentOutput,
    RESTfulAgentOutputType,
    RESTfulAgentText,
)
from typing import Generator, Optional, Tuple, cast
import requests
import logging


class RESTfulUserImplementedAgent(BaseAgent):
    def __init__(
        self,
        agent_config: RESTfulUserImplementedAgentConfig,
        logger=None,
    ):
        super().__init__(agent_config)
        if self.agent_config.generate_responses:
            raise NotImplementedError(
                "Use the WebSocket user implemented agent to stream responses"
            )
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        config = self.agent_config.respond
        try:
            agent_response = requests.request(
                method=config.method,
                url=config.url,
                json=RESTfulAgentInput(
                    human_input=human_input, conversation_id=conversation_id
                ).dict(),
                timeout=15,
            )
            assert agent_response.ok
            output = RESTfulAgentOutput.parse_obj(agent_response.json())
            response = None
            should_stop = False
            if output.type == RESTfulAgentOutputType.TEXT:
                response = cast(RESTfulAgentText, output).response
            elif output.type == RESTfulAgentOutputType.END:
                should_stop = True
            return response, should_stop
        except Exception as e:
            self.logger.error(f"Error in response from RESTful agent: {e}")
            return None, True

    def generate_response(self, human_input, is_interrupt: bool = False) -> Generator:
        """Returns a generator that yields a sentence at a time."""
        raise NotImplementedError
