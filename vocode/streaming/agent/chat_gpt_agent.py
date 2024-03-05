import asyncio
import json
import logging
import random

from typing import Any, Dict, List, Optional, Tuple, Union

import openai
from openai import AzureOpenAI, AsyncAzureOpenAI, OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Optional, Tuple
import aiohttp
import logging
from pydantic import BaseModel

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.actions import FunctionCall, FunctionFragment
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import (
    format_openai_chat_completion_from_transcript,
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

        self.agent_config.pending_action = None
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
            self.fclient = AsyncOpenAI(
                api_key="functionary", base_url=getenv("AI_API_BASE")
            )

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
            self.logger.setLevel(logging.DEBUG)

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
            # "stop": ["User:", "\n", "<|im_end|>", "?"],
            # just ?
            "stop": ["?"],
        }

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name

        if use_functions and self.functions:
            parameters["functions"] = self.functions
        return parameters

    def get_completion_parameters(  # MARKED
        self,
        messages: Optional[List] = None,
        use_functions: bool = True,
        affirmative_phrase: Optional[str] = "",
    ):
        assert self.transcript is not None
        formatted_completion = format_openai_chat_completion_from_transcript(
            self.transcript, self.agent_config.prompt_preamble
        )

        # add in the last turn and the affirmative phrase
        formatted_completion += f"<|im_start|>assistant\n{affirmative_phrase}"

        parameters: Dict[str, Any] = {
            "prompt": formatted_completion,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
            # "stop": ["User:", "\n", "<|im_end|>", "?"],
            # just ?
            "stop": ["?"],
        }

        if self.agent_config.azure_params is not None:
            parameters["engine"] = self.agent_config.azure_params.engine
        else:
            parameters["model"] = self.agent_config.model_name
            # parameters["model"] = "TheBloke/Nous-Hermes-2-Mixtral-8x7B-DPO-AWQ"

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
                pretty_tool_descriptions = ", ".join(tool_descriptions)
                chat = self.prepare_chat(latest_agent_response)
                stringified_messages = str(chat)
                system_message, transcript_message = self.prepare_messages(
                    pretty_tool_descriptions, stringified_messages
                )
                chat_parameters = self.get_chat_parameters(
                    messages=[system_message, transcript_message]
                )
                chat_parameters["model"] = "Qwen/Qwen1.5-72B-Chat-GPTQ-Int4"

                # check whether we should be executing an API call
                response = await self.aclient.chat.completions.create(**chat_parameters)
                is_classified_tool, tool_classification = self.get_tool_classification(
                    response, tools
                )
                # figure out the correct tool classification to use

                if is_classified_tool:
                    self.logger.info(
                        f"Initial API call classification: {tool_classification}"
                    )
                    await self.handle_tool_response(chat, tools, tool_classification)
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
                                "description": "The reason for transferring the call, limited to 120 characters",
                            }
                        },
                        "required": ["transfer_reason"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hangup_call",
                    "description": "Hangup the call if the assistant does not think the conversation is "
                    "appropriate to continue",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "end_reason": {
                                "type": "string",
                                "description": "The reason for ending the call, limited to 120 characters",
                            }
                        },
                        "required": ["end_reason"],
                    },
                },
            },
        ]

    def format_tool_descriptions(self, tools):
        return [
            f"'{tool['function']['name']}': {tool['function']['description']} (Required params: {', '.join(tool['function']['parameters']['required'])})"
            for tool in tools
        ]

    def prepare_chat(self, latest_agent_response):
        chat = format_openai_chat_messages_from_transcript(self.transcript)[1:]
        chat[-1] = {"role": "assistant", "content": latest_agent_response}
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

        self.logger.info(f"Final tool classification to trigger: {tool_classification}")
        is_classified_tool = tool_classification in [
            tool["function"]["name"].lower() for tool in tools
        ]
        return is_classified_tool, tool_classification

    async def handle_tool_response(self, chat, tools, tool_classification):
        tool_response = await self.fclient.chat.completions.create(
            model="meetkai/functionary-small-v2.2",
            messages=chat,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": tool_classification}},
        )
        tool_response = tool_response.choices[0]
        self.logger.info(f"The tool_response is {tool_response}")

        if tool_response.message.tool_calls:
            tool_call = tool_response.message.tool_calls[0]
            self.agent_config.pending_action = FunctionCall(
                name=tool_call.function.name, arguments=tool_call.function.arguments
            )

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
        if self.is_first_response and self.first_response:
            self.is_first_response = False
            text = self.first_response
        else:
            chat_parameters = self.get_chat_parameters()
            chat_completion = await self.aclient.chat.completions.create(
                **chat_parameters
            )
            text = chat_completion.choices[0].message.content
        return text, False

    async def generate_completion(
        self,
        human_input: str,
        affirmative_phrase: Optional[str],
        conversation_id: str,
        is_interrupt: bool = False,
        stream_output: bool = True,
    ) -> AsyncGenerator[Tuple[Union[str, FunctionCall], bool], None]:
        digits = [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ]
        # replace all written numbers with digits
        current_index = -1
        count = 0

        assert self.transcript is not None
        self.logger.debug(f"COMPLETION IS RESPONDING")
        chat_parameters = self.get_completion_parameters(
            affirmative_phrase=affirmative_phrase
        )
        # Prepare headers and data for the POST request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer 'EMPTY'",
        }
        prompt_buffer = chat_parameters["prompt"]
        words = prompt_buffer.split()
        new_words = []
        largest_seq = 0
        current_seq = 0
        last_digit_index = -1
        for i, word in enumerate(words):
            post = ""
            if "<|im_end|>" in word:
                pre = word.split("<|im_end|>")[0]
                post = "<|im_end|>" + word.split("<|im_end|>")[1]
                word = pre
            if word.lower() in digits:
                digit_str = str(digits.index(word.lower()))
                digit_str += post
                new_words.append(digit_str)
                current_seq += 1
                if current_seq > largest_seq:
                    largest_seq = current_seq
                    last_digit_index = i
            else:
                new_words.append(word + post)
                current_seq = 0
        if last_digit_index != -1:
            sequence_start = last_digit_index - largest_seq + 1
            insert_index = sum(len(w) + 1 for w in new_words[:sequence_start])
            if largest_seq == 10:
                number_sentence = f"(with {largest_seq} digits):"
            else:
                number_sentence = f"(with only {largest_seq} digits)"
            if largest_seq > 3:  # only provide nu
                prompt_buffer = (
                    " ".join(new_words[:sequence_start])
                    + f" {number_sentence} "
                    + " ".join(new_words[sequence_start:])
                )
        else:
            prompt_buffer = " ".join(new_words)

        prompt_buffer = prompt_buffer.replace("  ", " ")
        completion_buffer = ""
        tokens_to_generate = 120
        max_tokens = 120
        stop = ["?"]
        async with aiohttp.ClientSession() as session:
            base_url = getenv("AI_API_BASE")
            # Generate the first chunk
            while True:
                data = {
                    "model": chat_parameters["model"],
                    "prompt": prompt_buffer,
                    "stream": False,
                    "stop": [".", "?", "\n", ":"],
                    "max_tokens": tokens_to_generate,
                    "include_stop_str_in_output": True,
                }
                async with session.post(
                    f"{base_url}/completions", headers=headers, json=data
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        content = response_data["choices"][0]["text"].strip()
                        prompt_buffer += " " + content
                        prompt_buffer = prompt_buffer.strip().replace("  ", " ")
                        if (
                            content.endswith("?")
                            or content.endswith("\n")
                            or content.endswith(".")
                            or content.endswith(":")
                        ) and len(content.split()) > 2:
                            if stream_output:
                                self.logger.debug(f"Yielding first chunk: {content}")
                            yield (completion_buffer + " " + content), False
                            completion_buffer = ""
                            if content.endswith("?"):
                                return
                            break
                        else:
                            self.logger.debug(f"Got chunk: {content}")
                            completion_buffer += content
                    else:
                        self.logger.error(
                            f"Error while streaming from OpenAI1: {str(response)}"
                        )
                        return
            # Generate the second chunk
            data = {
                "model": chat_parameters["model"],
                "prompt": prompt_buffer,
                "stream": False,
                "stop": ["?"],
                "max_tokens": max_tokens,
                "include_stop_str_in_output": True,
            }
            self.logger.debug(f"Prompt buffer: {prompt_buffer}")
            self.logger.debug(f"data: {data}")
            async with session.post(
                f"{base_url}/completions", headers=headers, json=data
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    content = response_data["choices"][0]["text"].strip()
                    prompt_buffer += content
                    if stream_output:
                        self.logger.debug(f"Yielding second chunk: {content}")
                        # if its shorter than one word, add an uh in front of it
                        if len(content.split()) < 2:
                            chosen_word = random.choice("uh... um... er...".split())
                            content = chosen_word + " " + content
                        yield content, False
                else:

                    self.logger.error(
                        f"Error while streaming from OpenAI2: {str(response)}"
                    )

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
        self.logger.debug(f"CHAT IS RESPONDING")

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

        # Prepare headers and data for the POST request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer 'EMPTY'",
        }
        data = {
            "model": chat_parameters["model"],
            "messages": chat_parameters["messages"],
            "stream": True,
            "stop": ["?", "\n"],
            "include_stop_str_in_output": True,
        }

        # Perform the POST request to the OpenAI API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{getenv('AI_API_BASE')}/chat/completions",
                headers=headers,
                json=data,
                timeout=None,  # Stream endpoint; no timeout
            ) as response:
                if response.status == 200:
                    all_messages = []
                    messageBuffer = ""
                    async for line in response.content:
                        if line.strip():  # Ensure line is not just whitespace
                            try:
                                # find first and last { and } to extract the JSON
                                first_brace = line.find(b"{")
                                last_brace = line.rfind(b"}")
                                chunk = json.loads(
                                    line[first_brace : last_brace + 1].strip()
                                )
                                if "choices" in chunk and chunk["choices"]:
                                    for choice in chunk["choices"]:
                                        if (
                                            "delta" in choice
                                            and "content" in choice["delta"]
                                        ):
                                            message = choice["delta"]["content"]
                                            # if it contains any punctuation besides a comma, yield the buffer and the message and reset it
                                            # also check if, on split by space, it is longer than 2 words
                                            if (
                                                any(p in message for p in ".!?")
                                                and len(message.split(" ")) > 2
                                            ):
                                                messageBuffer += message
                                                all_messages.append(messageBuffer)
                                                yield messageBuffer, True
                                                messageBuffer = ""
                                            else:
                                                messageBuffer += message
                                            if (
                                                "finish_reason" in choice
                                                and choice["finish_reason"] == "stop"
                                            ):
                                                if len(messageBuffer) > 0:
                                                    all_messages.append(messageBuffer)
                                                    yield messageBuffer, True
                                                    messageBuffer = ""
                                                break
                            except json.JSONDecodeError:
                                # self.logger.error(
                                #     "JSONDecodeError: Received an empty line or invalid JSON."
                                # )
                                continue

                    if len(all_messages) > 0:
                        latest_agent_response = "".join(filter(None, all_messages))

                        await self.run_nonblocking_checks(
                            latest_agent_response=latest_agent_response
                        )
                else:
                    self.logger.error(
                        f"Error while streaming from OpenAI: {response.status}"
                    )
