from typing import Optional
from loguru import logger
from vocode.streaming.agent.base_agent import AgentResponse
from vocode.streaming.models.message import BaseMessage, LLMToken
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.synthesizer.synthesis_result import SynthesisResult
from vocode.streaming.utils.worker import InterruptibleAgentResponseEvent


class InputStreamingSynthesizer(BaseSynthesizer):
    def get_current_utterance_synthesis_result(self):
        raise NotImplementedError

    async def send_token_to_synthesizer(
        self,
        message: LLMToken,
        chunk_size: int,
    ):
        raise NotImplementedError

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        raise NotImplementedError

    async def _synthesize_agent_response(
        self, agent_response: AgentResponse
    ) -> SynthesisResult | None:
        maybe_synthesis_result: Optional[SynthesisResult] = None
        if isinstance(agent_response.message, LLMToken):
            logger.debug("Sending chunk to synthesizer")
            await self.send_token_to_synthesizer(
                message=agent_response.message,
                chunk_size=self.chunk_size,
            )
        elif isinstance(agent_response.message, BaseMessage):
            logger.debug("Synthesizing speech for message")
            maybe_synthesis_result = await self.create_speech_with_cache(
                agent_response.message,
                self.chunk_size,
                is_first_text_chunk=self.is_first_text_chunk,
                is_sole_text_chunk=agent_response.is_sole_text_chunk,
            )
        if not self.is_first_text_chunk:
            return
        elif isinstance(agent_response.message, LLMToken):
            return self.get_current_utterance_synthesis_result()
