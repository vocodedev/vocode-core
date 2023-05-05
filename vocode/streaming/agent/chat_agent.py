import logging
from typing import Optional, Tuple, Generator

from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.agent.base_agent import BaseAgent

from langchain.schema import ChatMessage, AIMessage
from langchain.memory import ConversationBufferMemory


class ChatAgent(BaseAgent):
    def __init__(
        self,
        agent_config: AgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config)
        self.logger = logger or logging.getLogger(__name__)
        self.memory = ConversationBufferMemory(return_messages=True)

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        raise NotImplementedError

    def generate_response(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        raise NotImplementedError

    def update_last_bot_message_on_cut_off(self, message: str):
        for memory_message in self.memory.chat_memory.messages[::-1]:
            if (
                isinstance(memory_message, ChatMessage)
                and memory_message.role == "assistant"
            ) or isinstance(memory_message, AIMessage):
                memory_message.content = message
                return
