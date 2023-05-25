import logging
from typing import AsyncGenerator, Optional, Tuple, Generator, TypeVar, Union

from vocode.streaming.models.agent import (
    AgentConfig,
    ChatAnthropicAgentConfig,
    ChatGPTAgentConfig,
)
from vocode.streaming.agent.base_agent import BaseAgent, RespondAgent

from langchain.schema import ChatMessage, AIMessage
from langchain.memory import ConversationBufferMemory

from vocode.streaming.models.events import Sender


ChatAgentConfigType = TypeVar(
    "ChatAgentConfigType", bound=Union[ChatGPTAgentConfig, ChatAnthropicAgentConfig]
)


class ChatAgent(RespondAgent[ChatAgentConfigType]):
    def __init__(
        self,
        agent_config: ChatAgentConfigType,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config)
        self.logger = logger or logging.getLogger(__name__)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        raise NotImplementedError

    def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError
