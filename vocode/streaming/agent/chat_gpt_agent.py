import asyncio
import json
import logging

from typing import Any, Dict, List, Optional, Tuple, Union

import openai
from openai import AzureOpenAI, AsyncAzureOpenAI, OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Optional, Tuple

import logging
from pydantic import BaseModel

from vocode import getenv
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

from telephony_app.models.call_type import CallType
from telephony_app.utils.call_information_handler import (
    update_call_transcripts,
    get_company_primary_phone_number,
    get_telephony_id_from_internal_id,
)
from telephony_app.utils.transfer_call_handler import transfer_call
from telephony_app.utils.twilio_call_helper import hangup_twilio_call


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
            agent_config=agent_config, action_factory=action_factory, logger=logger
        )

        if agent_config.azure_params:
            self.aclient = AsyncAzureOpenAI(
                api_version=agent_config.azure_params.api_version,
                api_key=getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=getenv("AZURE_OPENAI_API_BASE"),
            )

            self.client = AzureOpenAI(
                api_version=agent_config.azure_params.api_version,
                api_key=getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=getenv("AZURE_OPENAI_API_BASE"),
            )
        else:
            # mistral configs
            self.aclient = AsyncOpenAI(api_key="EMPTY", base_url=getenv("AI_API_BASE"))
            self.client = OpenAI(api_key="EMPTY", base_url=getenv("AI_API_BASE"))
            self.fclient = AsyncOpenAI(api_key="functionary", base_url=getenv("AI_API_BASE"))

            # openai.api_type = "open_ai"
            # openai.api_version = None

            # chat gpt configs
            # openai.api_type = "open_ai"
            # openai.api_base = "https://api.openai.com/v1"
            # openai.api_version = None
            # openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")

        if not self.client.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
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

        if self.logger:
            self.logger.setLevel(logging.INFO)

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
        ]

    def get_chat_parameters(
            self, messages: Optional[List] = None, use_functions: bool = True
    ):
        assert self.transcript is not None
        messages = messages or format_openai_chat_messages_from_transcript(
            self.transcript, self.agent_config.prompt_preamble
        )

        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
            "stop": ["User:", "\n", "<|im_end|>", "?"],
        }

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
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

    async def check_conditions(
            self, stringified_messages: str, conditions: List[str]
    ) -> List[str]:
        true_conditions = []

        tasks = []
        for condition in conditions:
            user_message = {
                "role": "user",
                "content": stringified_messages
                           + "\n\nNow, return either 'True' or 'False' depending on whether the condition: <"
                           + condition.strip()
                           + "> applies (True) to the conversation or not (False).",
            }

            preamble = "You will be provided a condition and a conversation. Please classify if that condition applies (True), or does not apply (False) to the provided conversation.\n\nCondition:\n"
            system_message = {"role": "system", "content": preamble + condition}
            combined_messages = [system_message, user_message]
            chat_parameters = self.get_chat_parameters(messages=combined_messages)
            task = self.aclient.chat.completions.create(**chat_parameters)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for response, condition in zip(responses, conditions):
            if "true" in response.choices[0].message.content.strip().lower():
                true_conditions.append(condition)

        return true_conditions

    async def run_nonblocking_checks(self, latest_agent_response: str):
        tools = self.get_tools()
        if self.agent_config.actions:
            try:
                tool_descriptions = self.format_tool_descriptions(tools)
                pretty_tool_descriptions = ', '.join(tool_descriptions)
                chat = self.prepare_chat(latest_agent_response)
                stringified_messages = str(chat)
                system_message, transcript_message = self.prepare_messages(pretty_tool_descriptions, stringified_messages)
                chat_parameters = self.get_chat_parameters(messages=[system_message, transcript_message])
                chat_parameters["model"] = "Qwen/Qwen1.5-72B-Chat-GPTQ-Int4"

                # check whether we should be executing an API call
                response = await self.aclient.chat.completions.create(**chat_parameters)
                tool_classification = self.get_tool_classification(response, tools)

                # figure out the correct tool classification to use
                if tool_classification:
                    return await self.handle_tool_response(chat, tools)
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")
        return

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "transfer_call",
                    "description": "Triggered when the agent agrees to transfer the call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "transfer_reason": {
                                "type": "string",
                                "description": "The reason for transferring the call, limited to 120 characters"
                            }
                        },
                        "required": ["transfer_reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "hangup_call",
                    "description": "Hangup the call if the assistant says goodbye",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "end_reason": {
                                "type": "string",
                                "description": "The reason for ending the call, limited to 120 characters"
                            }
                        },
                        "required": ["end_reason"]
                    }
                }
            }
        ]

    def format_tool_descriptions(self, tools):
        return [
            f"'{tool['function']['name']}': {tool['function']['description']} (Required params: {', '.join(tool['function']['parameters']['required'])})"
            for tool in tools
        ]

    def prepare_chat(self, latest_agent_response):
        chat = format_openai_chat_messages_from_transcript(self.transcript)[1:]
        chat[-1] = {'role': 'assistant', 'content': latest_agent_response}
        return chat

    def prepare_messages(self, pretty_tool_descriptions, stringified_messages):
        preamble = f"""You will be provided with a conversational transcript between a caller and the receiver's 
        assistant. During the conversation, the assistant has the following actions it can 
        take: {pretty_tool_descriptions}.\n 
        Your task is to infer whether, currently, the assistant is waiting for the caller to respond, or is 
        immediately going to execute an action without waiting for a response. Return the action name from the list 
        provided if the assistant is executing an action. If the assistant is waiting for a response, return 'None'. 
        Return a single word."""
        system_message = {"role": "system", "content": preamble}
        transcript_message = {"role": "user", "content": stringified_messages}
        return system_message, transcript_message

    def get_tool_classification(self, response, tools):
        tool_classification = response.choices[0].message.content.lower().strip()
        self.logger.info(f"Tool classification: {tool_classification}")
        return tool_classification in [tool["function"]["name"].lower() for tool in tools]

    async def handle_tool_response(self, chat, tools):
        tool_response = await self.fclient.chat.completions.create(
            model="meetkai/functionary-small-v2.2",
            messages=chat,
            tools=tools,
            tool_choice="auto"
        )
        tool_response = tool_response.choices[0]
        if tool_response.message.tool_calls:
            tool_call = tool_response.message.tool_calls[0]
            return FunctionCall(name=tool_call.function.name, arguments=tool_call.function.arguments)

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
            chat_completion = await self.aclient.chat.completions.create(
                **chat_parameters
            )
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
                vector_db_search_args = {
                    "query": self.transcript.get_last_user_message()[1],
                }

                has_vector_config_namespace = getattr(
                    self.agent_config.vector_db_config, "namespace", None
                )
                if has_vector_config_namespace:
                    vector_db_search_args[
                        "namespace"
                    ] = self.agent_config.vector_db_config.namespace.lower().replace(
                        " ", "_"
                    )

                docs_with_scores = await self.vector_db.similarity_search_with_score(
                    **vector_db_search_args
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
        stream = await self.aclient.chat.completions.create(**chat_parameters)
        all_messages = []

        async for message in collate_response_async(
                openai_get_tokens(stream), get_functions=True
        ):
            if not message:
                continue
            yield message, True
            all_messages.append(message)

        # add in a question mark if the last message doesn't end with a punctuation
        if all_messages and not (all_messages[-1][-1] in ".!?"):
            all_messages[-1] += "?"

        if len(all_messages) > 0:
            latest_agent_response = " ".join(filter(None, all_messages))
            api_function_call = await self.run_nonblocking_checks(latest_agent_response=latest_agent_response)
            if api_function_call:
                yield api_function_call, True
            self.logger.info(
                f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Agent: {latest_agent_response}"
            )
