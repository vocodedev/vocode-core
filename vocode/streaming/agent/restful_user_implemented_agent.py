from .base_agent import BaseAgent, RespondAgent
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
import aiohttp


class RESTfulUserImplementedAgent(RespondAgent[RESTfulUserImplementedAgentConfig]):
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
        self.logger = logger or logging.getLogger(__name__)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[Optional[str], bool]:
        config = self.agent_config.respond
        try:
            # TODO: cache session
            async with aiohttp.ClientSession() as session:
                payload = RESTfulAgentInput(
                    human_input=human_input, conversation_id=conversation_id
                ).dict()
                async with session.request(
                    config.method,
                    config.url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    assert response.status == 200
                    output: RESTfulAgentOutput = RESTfulAgentOutput.parse_obj(
                        await response.json()
                    )
                    output_response = None
                    should_stop = False
                    if output.type == RESTfulAgentOutputType.TEXT:
                        output_response = cast(RESTfulAgentText, output).response
                    elif output.type == RESTfulAgentOutputType.END:
                        should_stop = True
                    return output_response, should_stop
        except Exception as e:
            self.logger.error(f"Error in response from RESTful agent: {e}")
            return None, True
