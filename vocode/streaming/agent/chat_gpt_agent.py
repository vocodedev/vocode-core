import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Union, Type
from typing import AsyncGenerator, Optional, Tuple

import openai

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import RespondAgent, AgentInput, AgentResponseMessage
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.models.actions import FunctionCall
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.model import BaseModel
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.vector_db.factory import VectorDBFactory


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
            last_messages_cnt: int = 10

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
        self.first_response = (
            self.create_first_response(agent_config.expected_first_prompt)
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True
        self.last_messages_cnt = last_messages_cnt
        self.goodbye_phrase = goodbye_phrase
        if goodbye_phrase is not None:
            self.agent_config.end_conversation_on_goodbye = True

        if self.agent_config.vector_db_config:
            self.vector_db = vector_db_factory.create_vector_db(
                self.agent_config.vector_db_config
            )

        self.dialog_state = self.agent_config.dialog_state  # FIXME: ugly flow refactor it.

    @property
    def extract_belief_state(self):
        return self.agent_config.belief_state_prompt is not None

    async def is_goodbye(self, message: str):
        return self.goodbye_phrase.lower() in message.lower()

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
        all_responses = []
        async for response in responses:
            self.logger.debug("Got response from agent `%s`", response
                              )
            if isinstance(response, FunctionCall):
                function_call = response
                continue
            if isinstance(response, str):
                all_responses.append(response)

            if is_first_response:
                is_first_response = False
            self.logger.debug("Producing response `%s`", response)
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=response)),
                is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            )
            self.logger.debug("Produced response `%s`", response)

        if len(all_responses) > 0 and self.extract_belief_state:
            # FIXME: stardardize this
            formatted_responses = "\n".join(["BOT: " + response for response in all_responses])
            self.logger.info("Got responses from agent for dialog state extraction: %s", formatted_responses)
            belief_state = await self.get_dialog_state(formatted_responses)

            self.transcript.log_belief_state(belief_state)

            self.logger.info("Got belief state from agent: %s", belief_state)
            async for response in self.follow_response(formatted_responses):
                self.logger.info("Got follow up response from agent: `%s`", response)
                self.produce_interruptible_agent_response_event_nonblocking(
                    AgentResponseMessage(message=BaseMessage(text=response)),
                    is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
                )

        # TODO: implement should_stop for generate_responses
        if function_call and self.agent_config.actions is not None:
            await self.call_function(function_call, agent_input)

        return False

    def _parse_belief_state(self, belief_state: str) -> dict[str, str]:
        """
        Parse the belief state from the response.
        :param belief_state: The response from the model which must contain JSON parsable belief state.
        :return: The belief state extracted from the response.
        """

        # FIXME: is this needed?
        if 'DIALOG_STATE_UPDATE:' in belief_state:
            belief_state = belief_state.split('DIALOG_STATE_UPDATE:')[1].strip()

        try:
            # Data must be in JSON format
            return json.loads(belief_state)
        except ValueError:
            self.logger.error("No JSON data parsed in response.")
            # handle it better
            return {}

    async def get_dialog_state(self, bot_responses: str) -> dict[str, str]:
        """
        Extract the belief state by submitting the concatenated bot's responses to the model.

        Args:
        bot_responses (str): The concatenated responses from the bot.

        Returns:
        str: The belief state extracted by the model.
        """
        assert self.transcript is not None

        # Prepare the prompt with the concatenated bot responses
        # TODO: discuss management of history with other? How many messages we want to use?

        # TODO: add history here.
        # Prepare the chat parameters

        chat_parameters = self.get_chat_parameters(belief_state_extract=True)
        chat_parameters["messages"].append({"role": "assistant", "content": bot_responses})

        # Call the model
        chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)
        return self._parse_belief_state(chat_completion.choices[0].message.content)

    async def follow_response(self, override_dialog_state: Dict[str, Any],
                              combined_response: Optional[str] = None) -> AsyncGenerator:
        """
        Follow the response by the agent to the user's input.
        :param combined_response: The response by the agent to the user's input.
        :param override_dialog_state: The dialog state to override the current one.
        :return: The response by the agent to the user's input. Separated into individual sentences.
        """
        chat_parameters = self.get_chat_parameters(override_dialog_state=override_dialog_state)
        chat_parameters["stream"] = True
        # FIXME: rewrite it.
        if combined_response is not None:  # for example console app already has combined response in transcript so
            # we don't need to add it to the prompt
            chat_parameters["messages"].append({"role": "assistant", "content": combined_response})

        stream = await openai.ChatCompletion.acreate(**chat_parameters)
        async for message in collate_response_async(
                openai_get_tokens(stream), get_functions=True
        ):
            yield message

    @staticmethod
    def json_dump(d: dict):
        return json.dumps(d, indent=2, ensure_ascii=False)

    def get_dialog_state_str(self, state: BaseModel):
        data = state.dict()
        schema = state.schema()
        filtered = {}
        for prop, value in data.items():
            if not schema['properties'][prop].get('hidden', False):
                filtered[prop] = value

        return self.json_dump(filtered)

    def get_dialog_state_prompt_schema(self, state_class: Type[BaseModel]):
        data = state_class.schema()
        filtered = {}
        for prop, details in data['properties'].items():
            if not details.get('hidden', False):
                filtered[prop] = {key: details[key] for key in ('type', 'examples', 'enum') if key in details}

        return self.json_dump(filtered)

    def render_system_message(self, override_dialog_state: Optional[dict] = None):
        dialog_state_dict = self.dialog_state.dict()
        if override_dialog_state is not None:
            dialog_state_dict.update(**override_dialog_state)

        rendered_system_message = self.agent_config.prompt_preamble.render(
            dialog_state_extraction=False,
            dialog_state=dialog_state_dict,
            dialog_state_str=self.get_dialog_state_str(self.dialog_state),
            dialog_state_schema_str=self.get_dialog_state_prompt_schema(self.dialog_state.__class__),
            dialog_state_schema=self.dialog_state.schema(),
        )
        return rendered_system_message

    def render_extract_system_message(self, override_dialog_state: Optional[dict] = None):
        dialog_state_dict = self.dialog_state.dict()
        if override_dialog_state is not None:
            dialog_state_dict.update(**override_dialog_state)

        return self.agent_config.dialog_state_prompt.render(
            dialog_state_extraction=True,
            dialog_state=dialog_state_dict,
            dialog_state_str=self.get_dialog_state_str(self.dialog_state),
            dialog_state_schema_str=self.get_dialog_state_prompt_schema(self.dialog_state.__class__),
            dialog_state_schema=self.dialog_state.schema(),
        )

    def get_chat_parameters(self, messages: Optional[List] = None,
                            belief_state_extract: bool = False,
                            override_dialog_state: Optional[dict] = None):
        assert self.transcript is not None

        if belief_state_extract:
            messages = messages or format_openai_chat_messages_from_transcript(
                self.transcript, self.render_extract_system_message(override_dialog_state),
            )
        else:

            messages = messages or format_openai_chat_messages_from_transcript(
                self.transcript, self.render_system_message(override_dialog_state)
            )

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

        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
        }

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name

        if self.functions:
            parameters["functions"] = self.functions

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

        stream = await openai.ChatCompletion.acreate(**chat_parameters)
        async for message in collate_response_async(
                openai_get_tokens(stream), get_functions=True
        ):
            yield message
