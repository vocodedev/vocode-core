import os
from typing import Any, AsyncGenerator, Dict

import google.generativeai as genai
from google.generativeai.generative_models import _USER_ROLE
from google.generativeai.types import content_types, generation_types
import grpc

grpc.aio.init_grpc_aio()  # we initialize gRPC aio to avoid this issue: https://github.com/google-gemini/generative-ai-python/issues/207
import sentry_sdk
from loguru import logger

from vocode.streaming.action.abstract_factory import AbstractActionFactory
from vocode.streaming.action.default_factory import DefaultActionFactory
from vocode.streaming.agent.base_agent import GeneratedResponse, RespondAgent, StreamedResponse
from vocode.streaming.agent.streaming_utils import collate_response_async, stream_response_async
from vocode.streaming.models.agent import GoogleAIAgentConfig
from vocode.streaming.models.message import BaseMessage, LLMToken
from vocode.streaming.vector_db.factory import VectorDBFactory
from vocode.utils.sentry_utils import CustomSentrySpans, sentry_create_span


class GoogleAIAgent(RespondAgent[GoogleAIAgentConfig]):
    genai_chat: genai.ChatSession

    def __init__(
        self,
        agent_config: GoogleAIAgentConfig,
        action_factory: AbstractActionFactory = DefaultActionFactory(),
        vector_db_factory=VectorDBFactory(),
        **kwargs,
    ):
        super().__init__(
            agent_config=agent_config,
            action_factory=action_factory,
            **kwargs,
        )
        if not os.environ.get("GOOGLE_AI_API_KEY"):
            raise ValueError("GOOGLE_AI_API_KEY must be set in environment or passed in")
        self.genai_config = genai.configure(api_key=os.environ.get("GOOGLE_AI_API_KEY"))
        self.genai_model = genai.GenerativeModel(
            model_name=agent_config.model_name,
            generation_config=genai.GenerationConfig(
                max_output_tokens=agent_config.max_tokens,
                temperature=agent_config.temperature,
            ),
        )
        prompt_preamble = content_types.to_content(agent_config.prompt_preamble)
        prompt_preamble.role = _USER_ROLE
        self.genai_chat = self.genai_model.start_chat(history=[prompt_preamble])

    async def _create_google_ai_stream(self, message: str):
        return await self.genai_chat.send_message_async(message)

    async def google_ai_get_tokens(
        self, gen: generation_types.AsyncGenerateContentResponse
    ) -> AsyncGenerator[str, None]:
        async for msg in gen:
            yield msg.text

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
        bot_was_in_medias_res: bool = False,
    ) -> AsyncGenerator[GeneratedResponse, None]:
        if not self.transcript:
            raise ValueError("A transcript is not attached to the agent")
        try:
            first_sentence_total_span = sentry_create_span(
                sentry_callable=sentry_sdk.start_span, op=CustomSentrySpans.LLM_FIRST_SENTENCE_TOTAL
            )

            ttft_span = sentry_create_span(
                sentry_callable=sentry_sdk.start_span, op=CustomSentrySpans.TIME_TO_FIRST_TOKEN
            )
            stream = await self._create_google_ai_stream(human_input)
        except Exception as e:
            logger.error(
                f"Error while hitting Google AI with history: {self.genai_chat.history}",
                exc_info=True,
            )
            raise e

        response_generator = collate_response_async

        using_input_streaming_synthesizer = (
            self.conversation_state_manager.using_input_streaming_synthesizer()
        )
        if using_input_streaming_synthesizer:
            response_generator = stream_response_async
        async for message in response_generator(
            conversation_id=conversation_id,
            gen=self.google_ai_get_tokens(stream),
            sentry_span=ttft_span,
        ):
            if first_sentence_total_span:
                first_sentence_total_span.finish()

            ResponseClass = (
                StreamedResponse if using_input_streaming_synthesizer else GeneratedResponse
            )
            MessageType = LLMToken if using_input_streaming_synthesizer else BaseMessage

            if isinstance(message, str):
                yield ResponseClass(
                    message=MessageType(text=message),
                    is_interruptible=True,
                )
            else:
                yield ResponseClass(
                    message=message,
                    is_interruptible=True,
                )
