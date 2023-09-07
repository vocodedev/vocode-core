from typing import Optional, Union
from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.telephony.hosted.inbound_call_server import InboundCallServer
from vocode.streaming.models.agent import (
    RESTfulAgentEnd,
    RESTfulAgentInput,
    RESTfulAgentText,
    RESTfulUserImplementedAgentConfig,
)
from vocode.streaming.models.transcriber import (
    TranscriberConfig,
)
from vocode.streaming.models.synthesizer import SynthesizerConfig


class InboundCallUserAgentServer(InboundCallServer):
    def __init__(
        self,
        agent_config: RESTfulUserImplementedAgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        response_on_rate_limit: Optional[str] = None,
        vonage_config: Optional[VonageConfig] = None,
    ):
        super().__init__(
            agent_config=agent_config,
            transcriber_config=transcriber_config,
            synthesizer_config=synthesizer_config,
            response_on_rate_limit=response_on_rate_limit,
            vonage_config=vonage_config,
        )
        assert isinstance(
            agent_config, RESTfulUserImplementedAgentConfig
        ), "agent_config must be a RESTfulUserImplementedAgentConfig"
        self.app.post("/respond")(self.respond_rest)

    async def respond(
        self, human_input, conversation_id
    ) -> Union[RESTfulAgentText, RESTfulAgentEnd]:
        raise NotImplementedError

    async def respond_rest(
        self, request: RESTfulAgentInput
    ) -> Union[RESTfulAgentText, RESTfulAgentEnd]:
        return await self.respond(request.human_input, request.conversation_id)
