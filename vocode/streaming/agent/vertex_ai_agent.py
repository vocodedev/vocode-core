import logging
from typing import Optional, Tuple
from langchain import ConversationChain
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.agent import ChatVertexAIAgentConfig
from langchain.chat_models import ChatVertexAI
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)

from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain.memory import ConversationBufferMemory


class ChatVertexAIAgent(RespondAgent[ChatVertexAIAgentConfig]):
    def __init__(
        self,
        agent_config: ChatVertexAIAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)

        self.prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )

        self.llm = ChatVertexAI()

        self.memory = ConversationBufferMemory(return_messages=True)
        self.memory.chat_memory.messages.append(
            SystemMessage(content=self.agent_config.prompt_preamble)
        )

        self.conversation = ConversationChain(
            memory=self.memory, prompt=self.prompt, llm=self.llm
        )

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        text = self.conversation.predict(input=human_input)
        self.logger.debug(f"LLM response: {text}")
        return text, False
