import logging
import anthropic
from typing import Optional, Tuple, AsyncGenerator, Optional

from vocode.streaming.agent.utils import (
    find_last_punctuation,
    format_anthropic_chat_messages_from_transcript,
    get_sentence_from_buffer,
)

from vocode import getenv
from vocode.streaming.agent.chat_agent import ChatAgent
from vocode.streaming.models.agent import ChatAnthropicAgentConfig

SENTENCE_ENDINGS = [".", "!", "?"]


class ChatAnthropicAgent(ChatAgent[ChatAnthropicAgentConfig]):
    def __init__(
        self,
        agent_config: ChatAnthropicAgentConfig,
        logger: Optional[logging.Logger] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)

        anthropic_api_key = anthropic_api_key or getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed in"
            )
        if agent_config.initial_message:
            raise NotImplementedError("initial_message not implemented for Anthropic")

        self.anthropic_client = anthropic.Client(api_key=anthropic_api_key)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        prompt = format_anthropic_chat_messages_from_transcript(self.transcript)

        text = await self.anthropic_client.acompletion(
            prompt=prompt,
            stop_sequences=[anthropic.HUMAN_PROMPT],
            model=self.agent_config.model_name,
            max_tokens_to_sample=self.agent_config.max_tokens_to_sample,
        )

        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError("generate_response not implemented for Anthropic")
        # self.memory.chat_memory.messages.append(HumanMessage(content=human_input))

        # streamed_response = await self.anthropic_client.acompletion_stream(
        #     prompt=self.llm._convert_messages_to_prompt(
        #         self.memory.chat_memory.messages
        #     ),
        #     max_tokens_to_sample=self.agent_config.max_tokens_to_sample,
        #     model=self.agent_config.model_name,
        # )

        # bot_memory_message = AIMessage(content="")
        # self.memory.chat_memory.messages.append(bot_memory_message)

        # buffer = ""
        # async for message in streamed_response:
        #     completion = message["completion"]
        #     delta = completion[len(bot_memory_message.content + buffer) :]
        #     buffer += delta

        #     sentence, remainder = get_sentence_from_buffer(buffer)

        #     if sentence:
        #         bot_memory_message.content = bot_memory_message.content + sentence
        #         buffer = remainder
        #         yield sentence
        #     continue
