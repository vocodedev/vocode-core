import asyncio
import copy
import json
import logging
import random
import re
import string
import time

from vocode import getenv

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    PreTrainedTokenizerFast,
)

from typing import Any, Dict, List, Optional, Tuple, Union

import openai
from openai import AzureOpenAI, AsyncAzureOpenAI, OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Optional, Tuple
import aiohttp
import logging
from pydantic import BaseModel

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponseMessage,
    RespondAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.models.actions import (
    ActionInput,
    FunctionCall,
    ActionType,
    FunctionFragment,
)
from vocode.streaming.models.agent import CommandAgentConfig
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    format_tool_completion_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
    translate_message,
)
from vocode.streaming.transcriber.base_transcriber import (
    Transcription,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneCallAction,
    VonagePhoneCallAction,
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.utils.setup_command_r_tools import setup_command_r_tools
from vocode.streaming.utils.get_commandr_response import (
    format_command_function_completion_from_transcript,
    format_commandr_chat_completion_from_transcript,
    format_prefix_completion_from_transcript,
    get_commandr_response,
    get_commandr_response_chat_streaming,
    get_commandr_response_streaming,
)
from vocode.streaming.utils.get_qwen_response import (
    QWEN_MODEL_NAME,
    format_qwen_chat_completion_from_transcript,
    get_qwen_response,
)
from vocode.streaming.vector_db.factory import VectorDBFactory

from telephony_app.models.call_type import CallType
from telephony_app.utils.call_information_handler import (
    update_call_transcripts,
    get_company_primary_phone_number,
    get_telephony_id_from_internal_id,
)
from pydantic import BaseModel, Field

from telephony_app.utils.transfer_call_handler import transfer_call
from telephony_app.utils.twilio_call_helper import hangup_twilio_call

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer 'EMPTY'",
}


class EventLog(BaseModel):
    sender: Sender
    timestamp: float = Field(default_factory=time.time)

    def to_string(self, include_timestamp: bool = False) -> str:
        raise NotImplementedError


class CommandAgent(RespondAgent[CommandAgentConfig]):
    def __init__(
        self,
        agent_config: CommandAgentConfig,
        action_factory: ActionFactory = ActionFactory(),
        logger: Optional[logging.Logger] = None,
        openai_api_key: Optional[str] = None,
        vector_db_factory=VectorDBFactory(),
    ):
        super().__init__(
            agent_config=agent_config, action_factory=action_factory, logger=logger
        )
        self.tools = setup_command_r_tools(action_config=agent_config, logger=logger)
        self.tokenizer: PreTrainedTokenizerFast = AutoTokenizer.from_pretrained(
            "CohereForAI/c4ai-command-r-v01", trust_remote_code=False, use_fast=True
        )
        self.can_send = False
        self.conversation_id = None
        self.twilio_sid = None
        self.tool_message = ""
        self.block_inputs = False  # independent of interruptions, actions cannot be interrupted when a starting phrase is present
        self.streamed = False
        self.agent_config.pending_action = None
        self.stop = False
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
            self.aclient = AsyncOpenAI(
                api_key="EMPTY", base_url="http://148.64.105.83:4000/v1"
            )
            self.client = OpenAI(
                api_key="EMPTY", base_url="http://148.64.105.83:4000/v1"
            )
            self.fclient = AsyncOpenAI(
                api_key="functionary", base_url="http://148.64.105.83:4000/v1"
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
        reason: str = "",
        did_action: str = None,
    ):
        assert self.transcript is not None
        # add an
        formatted_completion, messages = (
            format_commandr_chat_completion_from_transcript(
                self.transcript,
                self.agent_config.prompt_preamble,
            )
        )
        # self.logger.debug(f"Formatted completion: {formatted_completion}")
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

    async def call_function(self, function_call: FunctionCall, agent_input: AgentInput):
        action_config = self._get_action_config(function_call.name)
        if action_config is None:
            self.logger.error(
                f"Function {function_call.name} not found in agent config, skipping"
            )
            return
        action = self.action_factory.create_action(action_config)
        params = json.loads(function_call.arguments)
        user_message_tracker = None
        if "user_message" in params:
            self.logger.info(f"User message: {params['user_message']}")
            user_message = params["user_message"]
            user_message_tracker = asyncio.Event()
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=user_message)),
                agent_response_tracker=user_message_tracker,
            )
        action_input: ActionInput
        if isinstance(action, VonagePhoneCallAction):
            assert (
                agent_input.vonage_uuid is not None
            ), "Cannot use VonagePhoneCallActionFactory unless the attached conversation is a VonageCall"
            action_input = action.create_phone_call_action_input(
                agent_input.conversation_id,
                params,
                agent_input.vonage_uuid,
                user_message_tracker,
            )
        elif isinstance(action, TwilioPhoneCallAction):
            assert (
                agent_input.twilio_sid is not None
            ), "Cannot use TwilioPhoneCallActionFactory unless the attached conversation is a TwilioCall"
            action_input = action.create_phone_call_action_input(
                agent_input.conversation_id,
                params,
                agent_input.twilio_sid,
                user_message_tracker,
            )
        else:
            action_input = action.create_action_input(
                conversation_id=agent_input.conversation_id,
                params=params,
                user_message_tracker=user_message_tracker,
            )
        event = self.interruptible_event_factory.create_interruptible_event(
            action_input, is_interruptible=action.is_interruptible
        )
        assert self.transcript is not None
        # self.transcript.add_action_start_log(
        #     action_input=action_input,
        #     conversation_id=agent_input.conversation_id,
        # )
        self.actions_queue.put_nowait(event)
        return

    async def gen_prefix(self):
        prefix_prompt_buffer = format_prefix_completion_from_transcript(
            self.transcript.event_logs,
        )

        async def call_prefixer_api(prompt: str) -> str:
            url = "http://azure6.ngrok.app/v1/completions"
            headers = {"Content-Type": "application/json"}
            data = {
                "model": "Cyleux/prefixer",
                "prompt": prompt,
                "max_tokens": 10,
                "temperature": 0.5,
                "stop": ["\n", "</s>"],
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        return response_json.get("choices", [{}])[0].get("text", "")
                    else:
                        self.logger.error(
                            f"Prefixer API call failed with status: {response.status}"
                        )
                        return ""

        prefix_response = await call_prefixer_api(
            prefix_prompt_buffer,
        )
        return prefix_response

    async def gen_tool_call(
        self, conversation_id
    ) -> Optional[Dict]:  # returns None or a dict if model should be called
        tools = self.tools

        if not self.agent_config.actions:
            self.logger.error(f"skipping tool call because agent has no actions")
            return None

        commandr_prompt_buffer, messageArray = (
            format_command_function_completion_from_transcript(
                self.tokenizer,
                self.transcript.event_logs,
                tools,
                self.agent_config.prompt_preamble,
            )
        )
        if "Do not provide" in messageArray[-1]["content"]:
            self.logger.info("Skipping tool use due to tool use.")
            return None  # TODO: investigate if this is why it needs to be prompted to do async tools
        use_qwen = self.agent_config.model_name.lower() == QWEN_MODEL_NAME.lower()

        commandr_response = None
        self.tool_message = ""
        frozen_transcript = self.transcript.copy()
        if self.agent_config.use_streaming and not use_qwen:
            commandr_response = ""
            current_utterance = ""
            self.logger.info(f"CALLING")
            if use_qwen:
                model_to_use = getenv("AI_MODEL_NAME_LARGE")
            else:
                model_to_use = self.agent_config.model_name
            first_tool_name = ""
            async for response_chunk in get_commandr_response_streaming(
                prompt_buffer=commandr_prompt_buffer,
                model=model_to_use,
                logger=self.logger,
            ):
                if self.stop:
                    self.logger.info("Stopping streaming")
                    self.stop = False
                    return None
                if (
                    '"tool_name":' in commandr_response
                    and not "DONE" in first_tool_name
                ):
                    if '"' not in first_tool_name:
                        first_tool_name += response_chunk
                    else:
                        if "answer" not in first_tool_name:
                            first_tool_name = first_tool_name.replace('",', "")
                            self.logger.info(f"First tool name: {first_tool_name}")
                            action_config = self._get_action_config(first_tool_name)
                            # check if starting_phrase exists and is true in the action config
                            if (
                                action_config.starting_phrase
                                and action_config.starting_phrase != ""
                            ):
                                # the value of starting_phrase is the message it says during the action
                                to_say_start = action_config.starting_phrase
                                self.produce_interruptible_agent_response_event_nonblocking(
                                    AgentResponseMessage(
                                        message=BaseMessage(text=to_say_start)
                                    )
                                )
                        first_tool_name = "DONE"
                stripped = response_chunk.rstrip()
                if len(stripped) != len(response_chunk):
                    response_chunk = stripped + " "
                response_chunk = response_chunk.replace("  ", " ")
                commandr_response += response_chunk
                split_pattern = re.compile(r"([.!?,]) ")
                split_pattern2 = re.compile(r'([.!?,])"')
                last_answer_index = commandr_response.rfind('"answer"')
                if (
                    last_answer_index != -1
                    and '"message": "' in commandr_response[last_answer_index:]
                    and not "}," in commandr_response[last_answer_index:]
                ):
                    current_utterance += response_chunk
                    if current_utterance.endswith("\\"):
                        self.logger.debug(
                            "current_utterance ends with a backslash, waiting for more data."
                        )
                        continue
                    # remove unescaped new line
                    current_utterance = re.sub(r"\\n", "\n", current_utterance)
                    # remove both kinds of brackets
                    current_utterance = re.sub(r"[{}]", "", current_utterance)
                    # current_utterance = re.sub(r"[^\w .,!?'@-]", "", current_utterance)
                    current_utterance = current_utterance.replace("  ", " ")
                    current_utterance = current_utterance.replace('"', "")
                    # split on pattern with punctuation and space, producing an interruptible of the stuff before (including the punctuation) and keeping the stuff after.
                    parts = split_pattern.split(current_utterance)
                    # join everything up to the last part
                    if (
                        len(parts) > 0
                        and len("".join(parts[:-1]).split(" ")) >= 3
                        and len("".join(parts[:-1]).split(" ")[-1])
                        > 3  # this is to avoid splitting on mr mrs
                        and any(char.isalnum() for char in "".join(parts[:-1]))
                    ):
                        self.streamed = (
                            True  # we said something so no need for fall back
                        )
                        output = "".join(
                            [
                                part + " " if part[-1] in ".,!?" else part
                                for part in parts[:-1]
                            ]
                        )
                        output = output.replace("] ```", "")
                        if len(output) > 0:
                            self.produce_interruptible_agent_response_event_nonblocking(
                                AgentResponseMessage(message=BaseMessage(text=output))
                            )
                            current_utterance = parts[-1]

            if len(current_utterance) > 0 and any(
                char.isalnum() for char in current_utterance
            ):
                # only keep the part before split pattern 2
                parts = split_pattern2.split(current_utterance)
                current_utterance = "".join(parts[:2])
                self.logger.info(f"Current utterance: {current_utterance}")
                current_utterance = current_utterance.replace("] ```", "")
                if len(current_utterance) > 0:
                    self.streamed = True  # we said something so no need for fall back

                    self.produce_interruptible_agent_response_event_nonblocking(
                        AgentResponseMessage(
                            message=BaseMessage(text=current_utterance)
                        )
                    )
                    current_utterance = ""

            # if "send_direct_response" in commandr_response:
            #     return None
        if not commandr_response:
            self.logger.info(f"There was not a streaming response")
            if self.agent_config.model_name.lower() == QWEN_MODEL_NAME.lower():
                commandr_response, qwen_response = await asyncio.gather(
                    get_commandr_response(
                        prompt_buffer=commandr_prompt_buffer,
                        model=getenv("AI_MODEL_NAME_LARGE"),
                        logger=self.logger,
                    ),
                    self.get_qwen_response_future(frozen_transcript),
                )
            else:
                commandr_response = await get_commandr_response(
                    prompt_buffer=commandr_prompt_buffer,
                    model=self.agent_config.model_name,
                    logger=self.logger,
                )
        elif self.agent_config.model_name.lower() == QWEN_MODEL_NAME.lower():
            qwen_response = await self.get_qwen_response_future(frozen_transcript)

        if not commandr_response.startswith("Action: ```json"):
            self.logger.error(f"ACTION RESULT DID NOT LOOK RIGHT: {commandr_response}")
        else:
            commandr_response_json_str = commandr_response[
                len("Action: ```json") :
            ].strip()
            commandr_response_json_str = commandr_response_json_str.replace(
                "```<|END_OF_TURN_TOKEN|>", ""
            )
            if commandr_response_json_str.endswith("```"):
                commandr_response_json_str = commandr_response_json_str[:-3].strip()
            try:
                commandr_response_data = json.loads(commandr_response_json_str)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"JSON DECODE ERROR: {e} with response: {commandr_response_json_str}"
                )
                return None
            except Exception as e:
                self.logger.error(
                    f"UNEXPECTED ERROR: {e} with response: {commandr_response_json_str}"
                )
                return None
            if not commandr_response_data:
                self.logger.error(
                    f"RESPONSE FORMAT ERROR: Expected a list with data, got: {commandr_response_data}"
                )
                return None

            if not isinstance(commandr_response_data, list):
                commandr_response_data = [commandr_response_data]
            tools_used = None
            self.logger.info(f"Response was: {commandr_response_data}")
            # iterate through the tools used to format them and set tool message
            # messy code since most stuff has been mvoed out
            for tool in commandr_response_data:
                tool_name = tool.get("tool_name")
                tool_params = tool.get("parameters")
                self.logger.info(f"running tool: {tool_name}")

                if tool_name == "answer":
                    self.logger.info(
                        f"No tool, model wants to directly respond: {tool_params}"
                    )
                    self.logger.info(json.dumps(tool_params))
                    if use_qwen:
                        self.logger.info(f"used Qwen for response: {qwen_response}")
                        self.tool_message = qwen_response.strip()
                    elif "message" in tool_params:
                        self.tool_message = tool_params["message"]
                        # self.logger.info(f"set tool message: {self.tool_message}")
                    # return None
                    continue
                elif tool_name and tool_params is not None:
                    try:

                        # self.can_send = False
                        if not tools_used:
                            tools_used = [
                                {
                                    "tool_name": tool_name,
                                    "tool_params": json.dumps(tool_params),
                                }
                            ]
                        else:
                            tools_used.append(
                                {
                                    "tool_name": tool_name,
                                    "tool_params": json.dumps(tool_params),
                                }
                            )

                    except Exception as e:
                        self.logger.error(f"ERROR CREATING FUNCTION CALL: {e}")
                        break  # If there's an error, we stop processing further tools
            self.can_send = False
            return tools_used
        return tools_used

    async def generate_completion(
        self,
        human_input: str,
        affirmative_phrase: Optional[str],
        conversation_id: str,
        is_interrupt: bool = False,
        stream_output: bool = True,
    ) -> str:
        if self.agent_config.language != "en-US":
            # Modify the transcript for the latest user message that matches human_input
            latest_human_message = next(
                (
                    event
                    for event in reversed(self.transcript.event_logs)
                    if event.sender == Sender.HUMAN and event.text.strip()
                ),
                None,
            )
            if latest_human_message:
                translated_message = translate_message(
                    self.logger,
                    latest_human_message.text,
                    self.agent_config.language,
                    "en-US",
                )
                self.logger.info(
                    f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Lead:{latest_human_message.text}"
                )
                latest_human_message.text = translated_message
        elif self.agent_config.language == "en-US":
            latest_human_message = next(
                (
                    event
                    for event in reversed(self.transcript.event_logs)
                    if event.sender == Sender.HUMAN and event.text.strip()
                ),
                None,
            )
            self.logger.info(
                f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Lead:{latest_human_message.text}"
            )

        assert self.transcript is not None

        tool_call = None
        if self.agent_config.actions:
            # prefix = await self.gen_prefix() TODO how to do
            tool_calls = await self.gen_tool_call(conversation_id)
            if tool_calls:
                tasks = []
                for tool_call in tool_calls:
                    if tool_call is not None:
                        name = tool_call["tool_name"]
                        params = eval(
                            tool_call["tool_params"]
                            .replace("null", "None")
                            .replace("false", "False")
                            .replace("true", "True")
                        )  # ensure we can interpret it as a dict
                        pretty_name = name.replace("_", " ")
                        to_replace = "\\n"
                        param_descriptions = [
                            f"'{value.replace(to_replace, ' ')}' as the '{key}'"
                            for key, value in params.items()
                        ]
                        if len(param_descriptions) > 1:
                            param_descriptions[-1] = "and " + param_descriptions[-1]
                        pretty_function_call = (
                            f"Tool Call: I'm going to '{pretty_name}', with "
                            + ", ".join(param_descriptions)
                        ) + "."
                        self.logger.info(
                            f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Agent: {pretty_function_call}"
                        )
                        self.logger.info(f"Name: {name}, Params: {params}")
                        action_config = self._get_action_config(name)
                        try:
                            action = self.action_factory.create_action(action_config)
                            action_input: ActionInput
                            if isinstance(action, TwilioPhoneCallAction):
                                assert (
                                    self.twilio_sid is not None
                                ), "Cannot use TwilioPhoneCallActionFactory unless the attached conversation is a TwilioCall"
                                action_input = action.create_phone_call_action_input(
                                    self.conversation_id,
                                    params,
                                    self.twilio_sid,
                                    user_message_tracker=None,
                                )
                            else:
                                action_input = action.create_action_input(
                                    conversation_id=self.conversation_id,
                                    params=params,
                                    user_message_tracker=None,
                                )

                            # check if starting_phrase exists and has content
                            if (
                                action_config.starting_phrase
                                and action_config.starting_phrase != ""
                            ):
                                # the value of starting_phrase is the message it says during the action
                                to_say_start = action_config.starting_phrase
                                if (
                                    not self.streamed
                                    and not self.agent_config.use_streaming
                                ):
                                    self.produce_interruptible_agent_response_event_nonblocking(
                                        AgentResponseMessage(
                                            message=BaseMessage(text=to_say_start)
                                        )
                                    )
                                # This may not be necessary with this mode but its how vocode works.
                                self.transcript.add_action_start_log(
                                    action_input=action_input,
                                    conversation_id=conversation_id,
                                )
                                # if we're using streaming, we need to block inputs until the tool calls are done
                                self.block_inputs = True

                                async def run_action_and_return_input(
                                    action, action_input, is_interrupt
                                ):
                                    action_output = await action.run(action_input)
                                    # also log the output
                                    pretty_function_call = f"Tool Response: {name}, Output: {action_output}"
                                    self.logger.info(
                                        f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Agent: {pretty_function_call}"
                                    )
                                    return action_input, action_output

                                # accumulate the tasks so we dont wait on each one sequentially
                                tasks.append(
                                    asyncio.create_task(
                                        run_action_and_return_input(
                                            action, action_input, is_interrupt
                                        )
                                    )
                                )
                            else:  # if streaming isn't enabled
                                await self.call_function(
                                    FunctionCall(
                                        name=name,
                                        arguments=json.dumps(params),
                                    ),
                                    TranscriptionAgentInput(
                                        transcription=Transcription(
                                            message="I am doing that for you now.",
                                            confidence=1.0,
                                            is_final=True,
                                            time_silent=0.0,
                                        ),
                                        conversation_id=self.conversation_id,
                                        twilio_sid=self.twilio_sid,
                                    ),
                                )
                                self.transcript.add_action_start_log(
                                    action_input=action_input,
                                    conversation_id=conversation_id,
                                )
                                if "qwen" in self.agent_config.model_name.lower():
                                    self.logger.info(
                                        f"Re-doing qwen due to tool call. Transcript: {self.transcript.to_string()}"
                                    )
                                    # this generates the starting phrase using qwen
                                    self.tool_message = await self.get_qwen_response_future(
                                        self.transcript  # not frozen because we want the latest tool call
                                    )
                                    # fallback mode will take care of the ending_phrase
                        except Exception as e:
                            self.logger.error(f"Error creating action: {e}")
                            self.tool_message = ""
                if len(tasks) > 0:
                    outputs = await asyncio.gather(*tasks)
                    finished = False
                    for input, output in outputs:
                        self.logger.info(f"Output: {output}")
                        self.transcript.add_action_finish_log(
                            action_input=input,
                            action_output=output,
                            conversation_id=conversation_id,
                        )
                        # if a tool produces an ending phrase, we say it out loud
                        if "ending_phrase" in output and not finished:
                            self.produce_interruptible_agent_response_event_nonblocking(
                                AgentResponseMessage(
                                    message=BaseMessage(text=output["ending_phrase"])
                                )
                            )
                            self.tool_message = output["ending_phrase"]
                            self.streamed = True  # and indicate we don't need to fall back to say something else
                self.block_inputs = False  # the tool calls are done which means we can continue with the conversation

        if self.streamed:
            self.streamed = False
            return "", True  # we said what we needed to say, no need to fall back
        if (
            self.agent_config.use_streaming
            and self.tool_message
            and len(self.tool_message) > 0
        ):
            if "qwen" in self.agent_config.model_name.lower():
                return (
                    self.tool_message,
                    True,
                )  # if qwen had something to say, we don't need to fall back
            self.logger.info(f"NO TOOL CALLS")
            return "", True  # we said what we needed to say, no need to fall back

        if len(self.tool_message) > 0:
            return self.tool_message, True
        if affirmative_phrase:
            chat_parameters = self.get_completion_parameters(
                affirmative_phrase=affirmative_phrase,
                did_action=tool_call,
                reason="",
            )
        else:
            chat_parameters = self.get_completion_parameters(
                did_action=tool_call, reason=""
            )

        prompt_buffer = chat_parameters["prompt"]

        prompt_buffer = prompt_buffer.replace("  ", " ")
        if len(prompt_buffer) == 0:
            self.logger.info("Prompt buffer is empty, returning")
            return
        if not prompt_buffer or len(prompt_buffer) < len(chat_parameters["prompt"]):
            prompt_buffer = chat_parameters["prompt"]

        if len(self.tool_message) > 0 and not self.agent_config.use_streaming:
            return self.tool_message, True
        elif len(self.tool_message) > 0 and self.agent_config.use_streaming:
            return "", True
        if "qwen" in self.agent_config.model_name.lower():
            model_to_use = getenv("AI_MODEL_NAME_LARGE")
        else:
            model_to_use = self.agent_config.model_name
        commandr_response = ""
        current_utterance = ""
        # log that we're in fallback mode
        self.logger.info(f"We're entering fallback mode now")
        if self.agent_config.use_streaming:
            async for response_chunk in get_commandr_response_chat_streaming(
                transcript=self.transcript,
                model=model_to_use,
                prompt_preamble=self.agent_config.prompt_preamble,
                logger=self.logger,
            ):
                if self.stop:
                    self.logger.info("Stopping streaming")
                    self.stop = False
                    return "", True
                stripped = response_chunk.rstrip()
                if len(stripped) != len(response_chunk):
                    response_chunk = stripped + " "
                response_chunk = response_chunk.replace("\n", " ")
                split_pattern = re.compile(r"([.!?,]) ")
                split_pattern2 = re.compile(r'([.!?])"')
                current_utterance += response_chunk
                # split on pattern with punctuation and space, producing an interruptible of the stuff before (including the punctuation) and keeping the stuff after.
                parts = split_pattern.split(current_utterance)
                if (
                    len(parts) > 0
                    and len("".join(parts[:-1]).split(" ")) >= 3
                    and len("".join(parts[:-1]).split(" ")[-1])
                    > 3  # this is to avoid splitting on mr mrs
                    and any(char.isalnum() for char in "".join(parts[:-1]))
                ):
                    output = "".join(
                        [
                            part + " " if part[-1] in ".,!?" else part
                            for part in parts[:-1]
                        ]
                    )
                    output = output.replace("] ```", "")
                    if len(output) > 0:
                        self.produce_interruptible_agent_response_event_nonblocking(
                            AgentResponseMessage(
                                message=BaseMessage(
                                    text=output,
                                )
                            )
                        )
                    current_utterance = parts[-1]
                    # log each part
                commandr_response += response_chunk
            if len(current_utterance) > 0 and any(
                char.isalnum() for char in current_utterance
            ):
                # only keep the part before split pattern 2
                parts = split_pattern2.split(current_utterance)
                current_utterance = "".join(parts[:2])
                current_utterance = current_utterance.replace("] ```", "")
                if len(current_utterance) > 0:
                    self.produce_interruptible_agent_response_event_nonblocking(
                        AgentResponseMessage(
                            message=BaseMessage(text=current_utterance)
                        )
                    )
            self.can_send = False
            return "", True
        else:
            commandr_response = await get_commandr_response(
                prompt_buffer=prompt_buffer,
                model=model_to_use,
                logger=self.logger,
            )
            self.logger.info(
                f"Commandr non-streaming fallback response: {commandr_response}"
            )
            return commandr_response, True

    async def get_qwen_response_future(self, transcript):
        response = ""
        qwen_prompt_buffer = format_qwen_chat_completion_from_transcript(
            transcript, self.agent_config.prompt_preamble
        )
        async for response_chunk in get_qwen_response(
            prompt_buffer=qwen_prompt_buffer, logger=self.logger
        ):
            response += response_chunk[0] + " "
            if response_chunk[1]:
                break
        return response

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
        data = {
            "model": chat_parameters["model"],
            "messages": chat_parameters["messages"],
            "stream": self.agent_config.use_streaming,
            "stop": ["?", "SYSTEM"],
            "include_stop_str_in_output": True,
        }

        # Perform the POST request to the OpenAI API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{getenv('AI_API_BASE')}/chat/completions",
                headers=HEADERS,
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
                                            message.replace("SYSTEM", "")
                                            # TODO Fix numbers bug $48.25 -> $ 48 err... 25
                                            # if it contains any punctuation besides a comma, yield the buffer and the message and reset it
                                            # also check if, on split by space, it is longer than 2 words
                                            if (
                                                any(p in message for p in ".!?")
                                                and len(message.split(" ")) > 2
                                            ):
                                                messageBuffer += message
                                                all_messages.append(messageBuffer)
                                                yield messageBuffer, True
                                                logging.info(
                                                    f"Yielded: {messageBuffer}"
                                                )
                                                messageBuffer = ""
                                            else:
                                                messageBuffer += message
                                            if (
                                                "finish_reason" in choice
                                                and choice["finish_reason"] == "stop"
                                            ):
                                                if len(messageBuffer.strip()) > 0:
                                                    all_messages.append(messageBuffer)
                                                    yield messageBuffer, True
                                                    messageBuffer = ""
                                                break
                            except json.JSONDecodeError:
                                # self.logger.error(
                                #     "JSONDecodeError: Received an empty line or invalid JSON."
                                # )
                                continue
                    # send out the last message
                    if len(messageBuffer.strip()) > 0:
                        all_messages.append(messageBuffer)
                        yield messageBuffer, True
                        messageBuffer = ""

                    if len(all_messages) > 0:
                        latest_agent_response = "".join(filter(None, all_messages))

                        await self.gen_tool_call(
                            latest_agent_response=latest_agent_response
                        )
                else:
                    self.logger.error(
                        f"Error while streaming from OpenAILast: {str(response)}"
                    )
