import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Dict, List, Union
from typing import AsyncGenerator, Optional, Tuple

import openai
import tiktoken

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import RespondAgent, AgentInput, AgentResponseMessage
from vocode.streaming.agent.response_validator import DefaultResponseValidator, ValidationResult
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.models.actions import FunctionCall
from vocode.streaming.models.agent import ChatGPTAgentConfig, ChatGPTAgentConfigOLD, CHAT_GPT_INITIAL_MESSAGE_MODEL_NAME
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.model import BaseModel
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.values_to_words import find_values_to_rewrite, response_to_tts_format
from vocode.streaming.vector_db.factory import VectorDBFactory

EXTRACTION_FIRST_N_ASSISTANT_SENTENCES = 2


@dataclass
class ConsoleChatResponse:
    message: str
    dialog_state_update: Optional[dict]
    raw_text: str
    failed_validation: Optional[ValidationResult] = None
    values_to_normalize: Optional[dict] = None

    @property
    def has_failed_validation(self):
        return self.failed_validation is not None

    @property
    def values_to_prompt_format(self) -> str:
        """Values to normalize in formatted as a list of key:value pairs
        :return: str with values to normalize
        """
        content = ""
        for key, value in self.values_to_normalize.items():
            if value is None:
                value = "null"
            content += f'{key}: {value}\n'
        return content


class ConsoleChatDecision(BaseModel):
    response: ConsoleChatResponse
    say_now_raw_text: Optional[str] = None
    say_now_script_location: Optional[str] = None
    follow_up_response_raw_text: Optional[str] = None
    retry: bool = None
    normalize: bool = False

    chat_parameters_text: Optional[List[Dict[str, Any]]] = None
    chat_parameters_dialog_state_update: Optional[List[Dict[str, Any]]] = None
    chat_parameters_normalization: Optional[List[Dict[str, Any]]] = None


def messages_from_transcript(transcript: Transcript, system_prompt: str):
    last_summary = transcript.last_summary
    if last_summary is not None:
        system_prompt += '\n THIS IS SUMMARY OF CONVERSATION SO FAR' + last_summary.text


class ChatGPTAgent(RespondAgent[ChatGPTAgentConfig]):
    def __init__(
            self,
            agent_config: ChatGPTAgentConfig,
            action_factory: ActionFactory = ActionFactory(),
            logger: Optional[logging.Logger] = None,
            openai_api_key: Optional[str] = None,
            vector_db_factory=VectorDBFactory(),
            goodbye_phrase: Optional[str] = "STOP CALL",
            call_script: Optional[Any] = None,

    ):
        super().__init__(
            agent_config=agent_config, action_factory=action_factory, logger=logger
        )
        if agent_config.azure_params:
            openai.api_type = agent_config.azure_params.api_type
            openai.api_base = getenv("AZURE_OPENAI_API_BASE")
            openai.api_version = agent_config.azure_params.api_version
            openai.api_key = getenv("AZURE_OPENAI_API_KEY")
            if agent_config.chat_gpt_functions_config.api_version is None:
                agent_config.chat_gpt_functions_config.api_version = "2023-07-01-preview"  # functions must have this or higher to work
        else:
            openai.api_type = "open_ai"
            openai.api_base = "https://api.openai.com/v1"
            openai.api_version = None
            openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.first_response = (
            self.create_first_response(agent_config.expected_first_prompt)
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True
        self.goodbye_phrase = goodbye_phrase
        # TODO: refactor it. Should use different logic
        # if goodbye_phrase is not None:
        #     self.agent_config.end_conversation_on_goodbye = True

        if self.agent_config.vector_db_config:
            self.vector_db = vector_db_factory.create_vector_db(
                self.agent_config.vector_db_config
            )

        if call_script is not None:
            self.call_script = call_script
        elif self.agent_config.call_script is not None:
            self.call_script = self.agent_config.call_script
        else:
            raise ValueError("call_script must be passed in or set in agent_config")

        self.response_validator = DefaultResponseValidator(max_length=self.agent_config.max_chars_check,
                                                           )

        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")  # FIXME: parametrize

        # logging parameters to get final chat_params from response generators
        self.last_chat_parameters_text: Optional[List[Dict[str, Any]]] = None
        self.last_chat_parameters_dialog_state_update: Optional[List[Dict[str, Any]]] = None
        self.last_chat_parameters_normalization: Optional[List[Dict[str, Any]]] = None

    @property
    def extract_belief_state(self):
        return self.call_script.dialog_state_prompt is not None

    async def is_goodbye(self, message: str):
        return self.goodbye_phrase.lower() in message.lower()

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string using tiktoken.
        """
        return len(self.tokenizer.encode(text))

    def trim_messages_to_fit(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Ensure that total tokens (messages + expected response) don't exceed max_tokens.
        Remove messages from the start (excluding the system prompt) if they do.
        """
        # Count tokens for each message once and store in a list
        token_counts = [self.count_tokens(message['content']) for message in messages]

        total_tokens = sum(token_counts)
        self.logger.debug("Total tokens: %s", total_tokens)

        # Calculate total tokens considering max response tokens
        total_tokens += self.agent_config.max_tokens
        self.logger.debug("Total tokens with max response tokens: %s", total_tokens)

        while total_tokens > self.agent_config.max_total_tokens and len(messages) > 1:
            # Remove the message from the front (excluding system prompt)
            removed_message = messages.pop(1)
            removed_token_count = token_counts.pop(1)

            self.logger.warning("Trimming messages to fit max_tokens. Message dropped: %s", removed_message["content"])
            total_tokens -= removed_token_count

        return messages

    def create_goodbye_detection_task(self, message: str):
        return asyncio.create_task(self.is_goodbye(message))

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
        ]

    async def _handle_initial_decision(self, chat_response: ConsoleChatResponse, decision: BaseModel):
        if decision.normalize:
            self.logger.warning("Normalizing dialog state")
            values_to_normalize = list(decision.response.values_to_normalize)
            normalized_dialog_state = await self.get_normalized_values(decision.response.values_to_prompt_format,
                                                                       values_to_normalize)
            normalized_dialog_state = {
                k: v for k, v in normalized_dialog_state.items()
                if k in values_to_normalize and k not in self.call_script.NORMALIZATION_CONTEXT_FIELDS
            }
            # merge normalized values into the original dialog state.
            chat_response.dialog_state_update = {**chat_response.dialog_state_update, **normalized_dialog_state}
            # Call decision callback again with normalized values
            decision = self.call_script.decision_callback(chat_response, normalize=False)
        return chat_response, decision

    def check_response(self, response: str) -> ValidationResult:
        validation_result = self.response_validator.validate(response)
        if not validation_result.valid:
            self.logger.warning("Response failed validation: %s", validation_result.reason)
        return validation_result

    async def handle_generate_response(
            self, transcription: Transcription, agent_input: AgentInput
    ) -> bool:
        conversation_id = agent_input.conversation_id

        self.logger.debug("AGENT: Got transcription from agent: %s", transcription.message)
        responses = self.generate_response(
            transcription.message,
            is_interrupt=transcription.is_interrupt,
            conversation_id=conversation_id,
        )
        is_first_response = True
        function_call = None
        failed_validation = None
        all_responses = []
        async for response in responses:
            self.logger.debug("Got response from agent `%s`", response
                              )
            if isinstance(response, FunctionCall):
                function_call = response
                continue
            if isinstance(response, str):
                validation_result = self.check_response(response)
                if not validation_result.valid:
                    failed_validation = validation_result
                    self.logger.warning("Response failed validation: %s", response)
                    break
                response = self.sanitize_response(response)
                values_to_rewrite = find_values_to_rewrite(response)
                response = response_to_tts_format(response, values_to_rewrite)
                all_responses.append(response)

            if is_first_response:
                is_first_response = False
            self.logger.debug("Producing response `%s`", response)
            self.transcript.log_gpt_message(response)
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=response)),
                is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            )
            self.logger.debug("Produced response `%s`", response)

        if self.extract_belief_state:
            # FIXME: stardardize this
            formatted_responses = "\n".join(["BOT: " + response for response in all_responses])

            self.logger.info("Got responses from agent for dialog state extraction: %s", formatted_responses)
            dialog_state_update = await self.get_dialog_state_update(
                '. '.join(all_responses[:EXTRACTION_FIRST_N_ASSISTANT_SENTENCES]))
            self.logger.info("Got dialog state update from agent: %s", dialog_state_update)
            full_response_text_only = ' '.join(all_responses)
            chat_response = ConsoleChatResponse(full_response_text_only, dialog_state_update,
                                                raw_text=full_response_text_only,
                                                failed_validation=failed_validation)
            decision: ConsoleChatDecision = self.call_script.decision_callback(chat_response)

            # Conditionally normalize the dialog state.
            chat_response, decision = await self._handle_initial_decision(chat_response, decision)
            all_follow_up_responses = []
            if decision.say_now_raw_text:
                all_follow_up_responses.append(decision.say_now_raw_text)
                self.produce_interruptible_agent_response_event_nonblocking(
                    AgentResponseMessage(message=BaseMessage(text=decision.say_now_raw_text)),
                    is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
                )

            elif decision.say_now_script_location:

                async for response in self.follow_response(override_dialog_state=dict(
                        script_location=decision.say_now_script_location), combined_response=formatted_responses):
                    response = self.sanitize_response(response)
                    values_to_rewrite = find_values_to_rewrite(response)
                    response = response_to_tts_format(response, values_to_rewrite)
                    all_follow_up_responses.append(response)
                    self.produce_interruptible_agent_response_event_nonblocking(
                        AgentResponseMessage(message=BaseMessage(text=response)),
                        is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
                    )

                    self.transcript.log_gpt_message(response, message_type="follow_up")

            decision.follow_up_response_raw_text = ' '.join(all_follow_up_responses)

            self.append_chat_params_to_decision_and_log_dialog_state(decision)

        # TODO: implement should_stop for generate_responses
        if function_call and self.agent_config.actions is not None:
            await self.call_function(function_call, agent_input)

        return False

    def append_chat_params_to_decision_and_log_dialog_state(self, decision: ConsoleChatDecision):
        decision.chat_parameters_text = self.last_chat_parameters_text
        decision.chat_parameters_dialog_state_update = self.last_chat_parameters_dialog_state_update
        decision.chat_parameters_normalization = self.last_chat_parameters_normalization

        self.last_chat_parameters_text: Optional[List[Dict[str, Any]]] = None
        self.last_chat_parameters_dialog_state_update: Optional[List[Dict[str, Any]]] = None
        self.last_chat_parameters_normalization: Optional[List[Dict[str, Any]]] = None

        self.transcript.log_dialog_state(self.call_script.dialog_state, decision)

    def _parse_dialog_state(self, belief_state: str) -> dict[str, str]:
        """
        Parse the belief state from the response.
        :param belief_state: The response from the model which must contain JSON parsable belief state.
        :return: The belief state extracted from the response.
        """

        try:
            # Data must be in JSON format
            return json.loads(belief_state)
        except ValueError:
            self.logger.error("No JSON data parsed in response.")
            # handle it better
            return {}

    @staticmethod
    def sanitize_response(response: str) -> str:
        result = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', response)
        result = result.replace("!", ".")
        return result

    async def get_normalized_values(self, content: str, keys_to_normalize: List[str]) -> dict[str, Any]:
        chat_parameters = self.get_chat_parameters(normalize=True, keys_to_normalize=keys_to_normalize)
        # TODO: discuss configs.
        chat_parameters["api_version"] = self.agent_config.chat_gpt_functions_config.api_version  # TODO: refactor it.
        chat_parameters["n"] = 3

        chat_parameters["messages"] = [chat_parameters["messages"][0]] + [{"role": "user", "content": content}]
        chat_parameters["messages"] = self.trim_messages_to_fit(chat_parameters["messages"])
        chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)

        self.last_chat_parameters_normalization = chat_parameters

        try:
            return json.loads(chat_completion.choices[0].message.content)
        except JSONDecodeError:
            return {}

    async def get_dialog_state_update(self, assistant_response_chunk: str) -> Dict[str, str]:
        """
        Extract the belief state by using transcript to get dialog history.
        :return: The belief state updated extracted from the response.
        """
        assert self.transcript is not None
        chat_parameters = self.get_chat_parameters(dialog_state_extract=True)
        # use base config but update it with functions config.
        chat_parameters = {**chat_parameters, **self.agent_config.chat_gpt_functions_config.dict()}

        chat_parameters["messages"] = [chat_parameters["messages"][0]] + \
                                      [{"role": "assistant", "content": self.transcript.last_assistant}]

        if self.transcript.last_user_message is not None:
            chat_parameters["messages"] += [{"role": "user", "content": self.transcript.last_user_message}, ]

        if assistant_response_chunk is not None:
            chat_parameters["messages"] += [{"role": "assistant", "content": assistant_response_chunk}]

        chat_parameters["messages"] = self.trim_messages_to_fit(chat_parameters["messages"])
        # Call the model
        chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)
        self.last_chat_parameters_dialog_state_update = chat_parameters
        return self._parse_dialog_state(chat_completion.choices[0].message.function_call.arguments)

    async def follow_response(self, override_dialog_state: Dict[str, Any],
                              combined_response: Optional[str] = None) -> AsyncGenerator:
        """
        Follow the response by the agent to the user's input.
        :param combined_response: The response by the agent to the user's input.
        :param override_dialog_state: The dialog state to override the current one.
        :return: The response by the agent to the user's input. Separated into individual sentences.
        """
        chat_parameters = self.get_chat_parameters(override_dialog_state=override_dialog_state)
        # FIXME: solve it somewhere else.
        chat_parameters["messages"][0]["content"] = re.sub(r'(\n\s*){2,}\n', '\n\n',
                                                           chat_parameters["messages"][0]["content"]).strip()
        chat_parameters["stream"] = True

        # Keeping only system prompt, because the model should only focus on rendering exactly the specified text and not anything else.
        # It would be nice to have flexiblity to connect more to previous context also with `combined_response`, but here we prefer to reset the state instead for now.
        chat_parameters["messages"] = [chat_parameters["messages"][0]]

        stream = await openai.ChatCompletion.acreate(**chat_parameters)
        async for message in collate_response_async(
                openai_get_tokens(stream), get_functions=True
        ):
            yield message

    @staticmethod
    def json_dump(d: dict):
        return json.dumps(d, indent=2, ensure_ascii=False)

    def get_chat_parameters(self, messages: Optional[List] = None,
                            dialog_state_extract: bool = False,
                            normalize: bool = False,
                            override_dialog_state: Optional[dict] = None,
                            keys_to_normalize: Optional[List[str]] = None):
        assert self.transcript is not None

        parameters: Dict[str, Any] = {
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
        }

        if dialog_state_extract:
            dialog_state_prompt, function = self.call_script.render_dialog_state_prompt_and_function(
                override_dialog_state=override_dialog_state,
            )
            messages = messages or format_openai_chat_messages_from_transcript(
                self.transcript, dialog_state_prompt
            )
            parameters.update({"functions": [function], "function_call": {"name": function["name"]}})

        elif normalize:
            prompt_preamble = self.call_script.render_normalization_prompt(keys_to_normalize)
            messages = [{"role": "system", "content": prompt_preamble}]
        else:
            messages = messages or format_openai_chat_messages_from_transcript(
                self.transcript, self.call_script.render_text_prompt(
                    override_dialog_state=override_dialog_state
                ))

        # select last 4 messages, always keep first message, make sure first message is not duplicated
        if len(messages) <= self.agent_config.last_messages_cnt:
            # If we have 4 or fewer messages, just use the original list.
            messages = messages
        else:
            # If we have more than 4 messages, include the first one and the last four.
            # This won't duplicate the first message because we're skipping the first part of the list.
            messages = messages[:1] + messages[-self.agent_config.last_messages_cnt:]

        # Commented for now because it will be used with belief state.
        # last_summary = self.transcript.last_summary
        # # TODO:refactor
        # if last_summary is not None:
        #     # insert into system prompt as new line
        #     if self.agent_config.prompt_preamble is not None:
        #         first_message = messages[0]
        #         # check if it is system message
        #         if first_message['role'] == 'system':
        #             first_message['content'] = self.agent_config.prompt_preamble + '\n' + last_summary.text
        #             # cut messages to self.last_messages_cnt
        #             if len(messages) - 1 > self.last_messages_cnt:
        #                 messages = [first_message] + messages[-self.last_messages_cnt:]
        #         else:
        #             self.logger.error('First message is not system message, not inserting summary. Something is wrong.')

        parameters.update(messages=messages)

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name

        return parameters

    def create_first_response(self, first_prompt):
        messages = (
                       [{"role": "system", "content": self.agent_config.prompt_preamble}]
                       if self.agent_config.prompt_preamble
                       else []
                   ) + ([{"role": "user", "content": first_prompt}] if first_prompt is not None else [])

        parameters = self.get_chat_parameters(messages)
        return openai.ChatCompletion.create(**parameters)

    def attach_transcript(self, transcript: Transcript):
        self.transcript = transcript

    async def respond(
            self,
            human_input,
            conversation_id: str,
            is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        start = time.time()
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
            chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)
            text = chat_completion.choices[0].message.content
        self.logger.debug(f"LLM response: {text}")
        end = time.time()
        self.logger.debug("Response took %s", end - start)
        return text, False

    async def generate_response(
            self,
            human_input: str,
            conversation_id: str,
            is_interrupt: bool = False,
    ) -> AsyncGenerator[Union[str, FunctionCall], None]:
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            yield cut_off_response
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
                    self.transcript, self.call_script.text_template
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
        # log number of tokens in prompt, messages and total
        # orig_prompt_tokens = len(self.agent_config.prompt_preamble.split())
        # self.logger.info(
        #     f"Number of tokens in original prompt: {orig_prompt_tokens}, gpt approx:{orig_prompt_tokens * 4 / 3}"
        # )
        # messages = chat_parameters["messages"]
        # updated_prompt_tokens = len(messages[0]["content"].split())
        # self.logger.info(
        #     f"Number of tokens in updated prompt: {updated_prompt_tokens}, gpt approx:{updated_prompt_tokens * 4 / 3}"
        # )
        # other_messages = messages[1:] if len(messages) > 1 else []
        # other_messages_tokens = sum(
        #     [len(message["content"].split()) for message in other_messages]
        # )
        # self.logger.info(
        #     f"Number of tokens in other messages: {other_messages_tokens}, gpt approx:{other_messages_tokens * 4 / 3}"
        # )
        # total_tokens = orig_prompt_tokens + other_messages_tokens
        # self.logger.info(
        #     f"Total number of tokens: {total_tokens}, gpt approx:{total_tokens * 4 / 3}"
        # )
        chat_parameters["messages"][0]["content"] = re.sub(r'(\n\s*){2,}\n', '\n\n',
                                                           chat_parameters["messages"][0]["content"]).strip()
        chat_parameters["messages"] = self.trim_messages_to_fit(chat_parameters["messages"])
        stream = await openai.ChatCompletion.acreate(**chat_parameters)
        self.last_chat_parameters_text = chat_parameters

        async for message in collate_response_async(
                openai_get_tokens(stream), get_functions=True
        ):
            yield message


class ChatGPTAgentOld(RespondAgent[ChatGPTAgentConfigOLD]):
    def __init__(
            self,
            agent_config: ChatGPTAgentConfigOLD,
            action_factory: ActionFactory = ActionFactory(),
            logger: Optional[logging.Logger] = None,
            openai_api_key: Optional[str] = None,
            vector_db_factory=VectorDBFactory(),
            response_predictor: Optional[Any] = None,
    ):
        super().__init__(
            agent_config=agent_config, action_factory=action_factory, logger=logger
        )
        if agent_config.azure_params:
            openai.api_type = agent_config.azure_params.api_type
            openai.api_base = getenv("AZURE_OPENAI_API_BASE")
            openai.api_version = agent_config.azure_params.api_version
            openai.api_key = getenv("AZURE_OPENAI_API_KEY")
        else:
            openai.api_type = "open_ai"
            openai.api_base = "https://api.openai.com/v1"
            openai.api_version = None
            openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.first_response = None
        self.is_first_response = True

        self.response_predictor = response_predictor
        self.seed = agent_config.seed
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
            self, messages: Optional[List] = None, use_functions: bool = True, ignore_assert: bool = False
    ):
        if not ignore_assert:
            assert self.transcript is not None
        messages = messages or format_openai_chat_messages_from_transcript(
            self.transcript, self.agent_config.prompt_preamble
        )

        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
        }

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name

        if use_functions and self.functions:
            parameters["functions"] = self.functions

        return parameters

    async def create_first_response(self, first_message_prompt: Optional[str] = None):
        system_prompt = first_message_prompt if first_message_prompt else self.agent_config.prompt_preamble
        messages = [{"role": "system", "content": system_prompt}]
        parameters = self.get_chat_parameters(messages)
        parameters["stream"] = True
        self.logger.info('Attempting to stream response for first message.')
        async for response, is_successful in self.__attempt_stream_with_retries(
                parameters, self.agent_config.timeout_seconds,
                max_retries=self.agent_config.max_retries):
            yield response, is_successful

    async def create_first_response_full(self, first_message_prompt: Optional[str] = None):
        system_prompt = first_message_prompt if first_message_prompt else self.agent_config.prompt_preamble
        messages = [{"role": "system", "content": system_prompt}]
        parameters = self.get_chat_parameters(messages, ignore_assert=True)
        parameters["stream"] = False
        self.logger.info('Attempting create response for the first message.')
        chat_completion = await openai.ChatCompletion.acreate(**parameters)
        return chat_completion.choices[0].message.content

    def attach_transcript(self, transcript: Transcript):
        self.transcript = transcript

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
            chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)
            text = chat_completion.choices[0].message.content
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def attempt_stream_response(self, chat_parameters, response_timeout):
        try:
            # Create the chat stream
            self.logger.info('attempt_stream_response')
            stream = await asyncio.wait_for(
                openai.ChatCompletion.acreate(**chat_parameters),
                timeout=self.agent_config.timeout_generator_seconds
            )
            self.logger.info('have attempt_stream_response')
            # Wait for the first message
            first_response = await asyncio.wait_for(
                collate_response_async(
                    openai_get_tokens(stream), get_functions=True
                ).__anext__(),
                timeout=response_timeout
            )
            self.logger.info('got first message')
            return stream, first_response
        except asyncio.TimeoutError:
            self.logger.info('got error timeout')
            return None, None

    async def __attempt_stream_with_retries(self, chat_parameters, initial_timeout, max_retries):
        timeout_increment = self.agent_config.retry_time_increment_seconds
        current_timeout = initial_timeout

        for attempt in range(max_retries + 1):
            stream, first_response = await self.attempt_stream_response(chat_parameters, current_timeout)

            if first_response is not None:
                self.logger.info(f'Stream attempt {attempt + 1} was successful.')
                yield first_response, True

                async for message in collate_response_async(
                        openai_get_tokens(stream), get_functions=True):
                    yield message, True
                return  # Exit the function after successful attempt

            else:
                self.logger.info(f'Stream attempt {attempt + 1} failed, retrying.')
                # Send filler words based on the attempt number minus one to ignore the first fail.
                if self.response_predictor is not None and attempt > 0:
                    # Ignore the first failed attempt.
                    yield self.response_predictor.get_retry_text(attempt - 1), False

                # Update timeout for the next attempt
                current_timeout += timeout_increment

        # If all retries fail
        self.logger.error('All stream attempts failed, giving up.')
        yield self.response_predictor.get_retry_failed(), False
        raise RuntimeError("Failed to get a timely response from OpenAI after retries.")

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
        chat_parameters["seed"] = self.seed

        self.logger.info('Attempting to stream response.')
        async for response, is_successful in self.__attempt_stream_with_retries(
                chat_parameters, self.agent_config.timeout_seconds,
                max_retries=self.agent_config.max_retries):
            yield response, is_successful
