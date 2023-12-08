import logging

from typing import Any, Dict, List, Optional, Tuple, Union

import openai
from openai import (AsyncAzureOpenAI, AzureOpenAI,
                    AsyncOpenAI, OpenAI)
from typing import AsyncGenerator, Optional, Tuple

import logging
from pydantic import BaseModel

from vocode import getenv
from vocode.streaming.utils.make_disfluencies import make_disfluency
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.actions import FunctionCall, FunctionFragment
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.vector_db.factory import VectorDBFactory
from vocode.streaming.agent.utils import replace_map_symbols

TIMEOUT_SECONDS = 5
TIMEOUT_SECONDS_BACKUP = 10
class ChatGPTAgent(RespondAgent[ChatGPTAgentConfig]):
    def __init__(
        self,
        agent_config: ChatGPTAgentConfig,
        action_factory: ActionFactory = ActionFactory(),
        logger: Optional[logging.Logger] = None,
        openai_api_key: Optional[str] = None,
        vector_db_factory=VectorDBFactory(),
    ):
        super().__init__(
            agent_config=agent_config, 
            action_factory=action_factory, 
            logger=logger
        )
        self.aclient = None
        self.client = None
        self.aclient_backup = None
        self.client_backup = None
        self.use_backup: bool = False 
        self.timeout_seconds = (self.agent_config.timeout_seconds 
                                if self.agent_config.timeout_seconds
                                else TIMEOUT_SECONDS)

        if agent_config.azure_params:
            self.logger.debug("Using Azure OpenAI")
            self.aclient = AsyncAzureOpenAI(
                api_version=agent_config.azure_params.api_version,
                azure_endpoint=getenv("AZURE_OPENAI_API_BASE"),
                timeout=self.timeout_seconds
            )
            self.client = AzureOpenAI(
                api_version=agent_config.azure_params.api_version,
                azure_endpoint=getenv("AZURE_OPENAI_API_BASE"),
                timeout=self.timeout_seconds,
            )
            if getenv("OPENAI_API_KEY"):
                self.aclient_backup = AsyncOpenAI(
                    timeout=TIMEOUT_SECONDS_BACKUP
                )
                self.client_backup = OpenAI(
                    timeout=TIMEOUT_SECONDS_BACKUP
                )
        elif getenv("OPENAI_API_KEY"):
            self.aclient = AsyncOpenAI(
                timeout=self.timeout_seconds
            )
            self.client = OpenAI(
                timeout=self.timeout_seconds
            )
        else:
            raise ValueError("AZURE_OPENAI_API_KEY or OPENAI_API_KEY must be set in environment")
        self.first_response = (
            self.create_first_response(agent_config.expected_first_prompt)
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True

        if self.agent_config.vector_db_config:
            self.vector_db = vector_db_factory.create_vector_db(
                self.agent_config.vector_db_config
            )

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
        ]

    def get_chat_parameters(
        self, 
        messages: Optional[List] = None, 
        use_functions: bool = True,
    ):
        assert self.transcript is not None
        messages = messages or format_openai_chat_messages_from_transcript(
            self.transcript, 
            self.agent_config.prompt_preamble,
            self.agent_config.prompt_epilogue
        )
        self.logger.debug(f"Last four LLM input messages: {messages[-4:]}")
        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
            "stop": self.agent_config.stop_tokens,
            "frequency_penalty": self.agent_config.frequency_penalty,
            "stream": True
        }

        if self.agent_config.azure_params is not None:
            parameters["model"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name

        if use_functions and self.functions:
            parameters["functions"] = self.functions

        return parameters

    def create_first_response(self, first_prompt):
        messages = [
            (
                [{"role": "system", "content": self.agent_config.prompt_preamble}]
                if self.agent_config.prompt_preamble
                else []
            )
            + [{"role": "user", "content": first_prompt}]
        ]

        parameters = self.get_chat_parameters(messages)
        return self.client.chat.completions.create(**parameters)

    def attach_transcript(self, transcript: Transcript):
        self.transcript = transcript

    async def get_stream_response(
            self, 
            chat_parameters: dict,
            max_retries: int = 3
        ):
        chat_parameters_backup = chat_parameters.copy()
        chat_parameters_backup["model"] = self.agent_config.model_name
        for attempt in range(max_retries+1):
            self.logger.debug(f"Attempt {attempt} to get stream response")
            if not self.use_backup:
                try:
                    stream = await self.aclient.chat.completions.create(**chat_parameters)
                    return stream
                except Exception as e1:
                    self.use_backup = True
                    self.logger.debug(f"Error in main OpenAI client: {type(e1).__name__}")
            if self.aclient_backup: 
                self.logger.debug("Using backup client")
                try:
                    stream = await self.aclient_backup.chat.completions.create(**chat_parameters_backup)
                    return stream
                except Exception as e2:
                    self.logger.error(f"Error in OpenAI backup client: {e2}")
                    continue
            else:
                self.logger.error("No backup client available")
                continue

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        assert self.transcript is not None
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            return cut_off_response, False
        self.logger.debug("LLM responding to human input")
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            text = self.first_response
        else:
            chat_parameters = self.get_chat_parameters()
            chat_completion = await self.aclient.chat.completions.create(**chat_parameters)
            text = chat_completion.choices[0].message.content
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
        self,
        human_input: str,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[Tuple[Union[str, FunctionCall], bool], None]:
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            yield cut_off_response, False
            return
        assert self.transcript is not None

        chat_parameters = {}
        if self.agent_config.vector_db_config:
            try:
                docs_with_scores = await self.vector_db.similarity_search_with_score(
                    self.transcript.get_last_user_message()[1]
                )
                docs_with_scores_str = "\n\n".join(
                    [
                        "Document: "
                        + doc[0].metadata["source"]
                        + f" (Confidence: {doc[1]})\n"
                        + doc[0].lc_kwargs["page_content"].replace(r"\n", "\n")
                        for doc in docs_with_scores
                    ]
                )
                vector_db_result = f"Found {len(docs_with_scores)} similar documents:\n{docs_with_scores_str}"
                messages = format_openai_chat_messages_from_transcript(
                    self.transcript, self.agent_config.prompt_preamble
                )
                messages.insert(
                    -1, vector_db_result_to_openai_chat_message(vector_db_result)
                )
                chat_parameters = self.get_chat_parameters(messages)
            except Exception as e:
                self.logger.error(f"Error while hitting vector db: {e}", exc_info=True)
                chat_parameters = self.get_chat_parameters()
        else:
            chat_parameters = self.get_chat_parameters()
        chat_parameters["stream"] = True
        self.logger.debug(f"Starting LLM stream...")
        stream = await self.get_stream_response(chat_parameters)
        # stream = await self.aclient.chat.completions.create(**chat_parameters)
        self.logger.debug(f"Got LLM stream...")
        try:
            async for message in collate_response_async(
                openai_get_tokens(stream, logger=self.logger), 
                get_functions=True,
                logger=self.logger
            ):
                if isinstance(message, str):
                    if self.agent_config.character_replacement_map:
                        message = replace_map_symbols(message, self.agent_config.character_replacement_map)
                    if self.agent_config.remove_exclamation:
                        # replace ! by . because it sounds better when speaking.
                        message = message.replace('!','.')
                    if self.agent_config.add_disfluencies:
                        # artificially add disfluencies to message
                        message = make_disfluency(message)
                yield message, True
        except Exception as e:
            self.logger.error(f"Error in LLM stream: {e}", exc_info=True)
            if not self.use_backup:
                self.logger.error("Switching to backup client")
                self.use_backup = True
