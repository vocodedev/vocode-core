from vocode.streaming.transcriber.base_transcriber import Transcription
from .base_agent import (
    AgentResponseMessage,
    BaseAsyncAgent,
    OneShotAgentResponse,
    StopAgentResponseMessage,
    TextAgentResponseMessage,
)
from ..models.agent import (
    RESTfulAgentEnd,
    RESTfulUserImplementedAgentConfig,
    RESTfulAgentInput,
    RESTfulAgentOutput,
    RESTfulAgentText,
)
import logging
import aiohttp


class RESTfulUserImplementedAgent(BaseAsyncAgent):
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

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)
        response_message = await self.get_response_message(transcription)
        self.add_agent_response_to_output_queue(OneShotAgentResponse(message=response_message))

    async def get_response_message(self, transcription: Transcription) -> AgentResponseMessage:
        config = self.agent_config.respond
        try:
            async with aiohttp.ClientSession() as session:
                payload = RESTfulAgentInput(
                    human_input=transcription.message
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
                    if isinstance(output, RESTfulAgentText):
                        return TextAgentResponseMessage(text=output.response)
                    elif isinstance(output, RESTfulAgentEnd):
                        return StopAgentResponseMessage()
                    else:
                        raise Exception(f"Unknown RESTful response type: {output}")
        except Exception as e:
            self.logger.error(f"Error in response from RESTful agent: {e}")
            return StopAgentResponseMessage()
