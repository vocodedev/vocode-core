import asyncio
import json
import logging
import re
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from vocode.streaming.agent.base_agent import (
    RespondAgent,
    AgentInput,
    AgentResponseMessage,
)
from vocode.streaming.models.agent import CommandAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.models.events import Sender
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from vocode import getenv
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneCallAction,
    VonagePhoneCallAction,
)

from vocode.streaming.agent.utils import (
    translate_message,
)
from vocode.streaming.utils.find_sparse_subarray import find_last_sparse_subarray


class StateMachine(BaseModel):
    states: Dict[str, Any]
    initial_state_id: str


# thing to say, switch/continue/pause
class BranchDecision(Enum):
    PAUSE = 1
    SWITCH = 2
    CONTINUE = 3


def parse_llm_dict(s):
    # if its already a dict return
    if isinstance(s, dict):
        return s

    # replace all double quotes with single quotes
    s = s.replace('"', "'")
    # remove all new lines and extra spacing
    s = s.replace("\n", "").replace("  ", " ").replace("  ", " ")
    # replace without space
    s = s.replace("','", "', '")
    result = {}
    input_string = s.strip("{}")
    pairs = input_string.split("', '")

    for pair in pairs:
        if ":" in pair:
            key, value = pair.split(":", 1)
            key = key.strip().strip("'")
            value = value.strip().strip("'")

            if value.isdigit():
                value = int(value)

            result[key] = value

    return result


def get_state(state_id_or_label: str, state_machine):
    state_id = (
        state_machine["labelToStateId"][state_id_or_label]
        if state_id_or_label in state_machine["labelToStateId"]
        and state_machine["labelToStateId"][state_id_or_label]
        else state_id_or_label
    )
    if not state_id:
        return None
    state = state_machine["states"][state_id]
    if not state:
        return None
    if state["type"] == "crossroads":
        raise Exception("crossroads state is deprecated")
    return state


def translate_to_english(
    ai_profile_language: str, text: str, logger: logging.Logger
) -> str:
    if ai_profile_language == "en-US":
        return text

    translated_message = translate_message(
        logger,
        text,
        ai_profile_language,
        "en-US",
    )
    return translated_message


async def handle_question(
    state,
    go_to_state: Callable[[str, List[str]], Awaitable[Any]],
    speak_message: Callable[[Any], None],
    logger: logging.Logger,
    state_history: List[Any]
):

    await speak_message(state["question"])

    async def resume(human_input):
        logger.info(f"continuing at {state['id']} with user response {human_input}")
        return await go_to_state(get_default_next_state(state), state_history + [state])

    return resume


async def handle_options(
    state: Any,
    go_to_state: Callable[[str, List[str]], Awaitable[Any]],
    speak: Callable[[str], None],
    call_ai: Callable[[str, Dict[str, Any], Optional[str]], Awaitable[str]],
    state_machine: Any,
    get_chat_history: Callable[[], List[Tuple[str, str]]],
    logger: logging.Logger,
    state_history: List[Any],
):
    last_user_message_index = None
    last_user_message = None
    last_bot_message = state_machine["states"]["start"]["start_message"]["message"]
    next_state_history = state_history + [state]
    action_result_after_user_spoke = None
    # Iterate through the chat history to find the last user message
    for i, (role, msg) in enumerate(reversed(get_chat_history())):
        if last_user_message_index is None and role == "human" and msg:
            last_user_message_index = len(get_chat_history()) - i - 1
            last_user_message = msg
            break

    # If a user message was found, iterate again to find the last bot message before the user message
    if last_user_message_index is not None:
        for i, (role, msg) in enumerate(
            reversed(get_chat_history()[:last_user_message_index])
        ):
            if role == "message.bot" and msg:
                last_bot_message = msg
                break

    action_result_after_user_spoke = None
    if last_user_message_index:
        for i, (role, msg) in enumerate(
            get_chat_history()[last_user_message_index + 1 :]
        ):
            if role == "action-finish" and msg:
                action_result_after_user_spoke = msg
                break
    tool = {"condition": "[insert the number of the condition that applies]"}

    default_next_state = get_default_next_state(state)
    response_to_edge = {}
    ai_options = []
    prev_state = state_history[-1] if state_history else None
    logger.info(f"state edges {state}")
    edges = [
        edge
        for edge in state["edges"]
        if (edge.get("aiLabel") or edge.get("aiDescription"))
    ]

    # add disambiguation edges unless we're at in the start state or an action just finished
    logger.info(
        f"araus = {action_result_after_user_spoke} state id is {state['id']} and startingStateId is {state_machine['startingStateId']}"
    )
    if (
        state["id"] != state_machine["startingStateId"]
        and (prev_state and prev_state["type"] == "question")
        and not action_result_after_user_spoke
    ):
        edges.append(
            {
                "destStateId": state_machine["startingStateId"],
                "aiLabel": "switch",
                "aiDescription": f"user no longer needs help with '{state['id'].split('::')[0]}'",
            }
        )
        edges.append(
            {
                "destStateId": default_next_state,
                "aiLabel": "continue",
                "aiDescription": f"user still needs help with '{state['id'].split('::')[0]}' but no condition applies",
            }
        )
        # extra edge if this state was part of a question section
        if "question" in state["id"].split("::")[-2]:
            edges.append(
                {
                    "destStateId": default_next_state,
                    "speak": True,
                    "aiLabel": "question",
                    "aiDescription": "user seems confused or unsure",
                },
            )

    logger.info(f"edges {edges}")
    logger.info(f"original edges {state['edges']}")
    index = 0
    for index, edge in enumerate(edges):
        if "isDefault" not in edge or not edge["isDefault"]:
            response_to_edge[index] = edge
            if edge.get("aiLabel"):
                response_to_edge[edge["aiLabel"]] = edge

            ai_options.append(
                f"{index}: {edge.get('aiDescription', None) or edge.get('aiLabel', None)}"
            )
    if len(ai_options) == 0:
        raise Exception("invalid options state with no options")

    ai_options_str = "\n".join(ai_options)
    prompt = (
        f"Bot's last statement: '{last_bot_message}'\n"
        f"User's response: '{last_user_message}'\n"
        f"{'Last tool output: ' + action_result_after_user_spoke if action_result_after_user_spoke else ''}\n\n"
        "Identify the number associated with the most fitting condition from the list below:\n"
        f"{ai_options_str}\n\n"
        "Always return a number from the above list. Return the number of the condition that best applies."
    )
    logger.info(f"AI prompt constructed: {prompt}")
    response = await call_ai(
        prompt,
        tool,
    )

    logger.info(f"Chose condition: {response}")
    response = response[response.find("{") : response.rfind("}") + 1]

    try:
        condition = parse_llm_dict(response)["condition"]
        # only int if its not already
        if isinstance(condition, str):
            condition = int(condition)
        next_state_id = response_to_edge[condition]["destStateId"]
        if response_to_edge[condition].get("speak"):
            # we would call ai and speak here
            prompt = (
                f"You last stated: '{last_bot_message}', to which the user replied: '{last_user_message}'.\n\n"
                f"You are already engaged in the following process: {state['id'].split('::')[0]}\n"
                "Right now, you are pausing the process to assist the confused user.\n"
                "Respond as follows: If the user didn't answer, politely restate the question and ask for a clear answer.\n"
                "- If the user asked a question, provide a concise answer and then pause.\n"
                "- Ensure not to suggest any actions or offer alternatives.\n"
            )
            # we do not care what it has to say when switching or continuing
            output = await call_ai(prompt, {})
            speak(output)

            async def resume(human_input):
                logger.info(
                    f"continuing at {state['id']} with user response {human_input}"
                )
                return await go_to_state(state["id"], next_state_history)

            return resume
        return await go_to_state(next_state_id, next_state_history)
    except Exception as e:
        logger.error(f"Agent chose no condition: {e}. Response was {response}")
        return await go_to_state(default_next_state, next_state_history)


def get_default_next_state(state):
    if state["type"] != "options":
        return state["edge"]
    for edge in state["edges"]:
        if "isDefault" in edge and edge["isDefault"]:
            return edge["destStateId"]


class StateAgent(RespondAgent[CommandAgentConfig]):
    def __init__(
        self,
        agent_config: CommandAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)
        self.state_machine = self.agent_config.user_json_prompt["converted"]
        self.current_state = None
        self.resume = lambda _: self.handle_state(self.state_machine["startingStateId"], [])
        self.can_send = False
        self.conversation_id = None
        self.twilio_sid = None
        self.block_inputs = False  # independent of interruptions, actions cannot be interrupted when a starting phrase is present
        self.stop = False
        self.visited_states = {self.state_machine["startingStateId"]}
        self.chat_history = [("message.bot", self.agent_config.initial_message)]
        self.base_url = getenv("AI_API_HUGE_BASE")
        self.model = (
            self.agent_config.model_name
            or "accounts/fireworks/models/qwen2-72b-instruct"
        )
        self.client = AsyncOpenAI(
            base_url=self.base_url,
        )

        self.overall_instructions = (
            self.agent_config.prompt_preamble
            + "\n"
            + self.state_machine["states"]["start"]["instructions"]
        )
        self.label_to_state_id = self.state_machine["labelToStateId"]
        #     self.state_machine.initial_state_id
        # )["instructions"]

    def update_history(self, role, message):
        self.chat_history.append((role, message))
        if role == "message.bot":
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=message))
            )

    async def generate_completion(
        self,
        affirmative_phrase: Optional[str],
        conversation_id: str,
        human_input: str,
        is_interrupt: bool = False,
        stream_output: bool = True,
    ):
        self.update_history("human", human_input)
        self.logger.info(
            f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Lead:{human_input}"
        )
        if self.resume:
            self.resume = await self.resume(human_input)

        return "", True

    async def print_start_message(self, state, start: bool):
        if start and "start_message" in state:
            await self.print_message(state["start_message"])

    async def print_message(self, message):
        if message["type"] == "verbatim":
            self.update_history("message.bot", message["message"])
        else:
            guide = message["description"]
            await self.guided_response(guide)

    # recursively traverses the state machine
    # if it returns a function, call that function on the next human input to resume traversal
    async def handle_state(self, state_id_or_label: str, state_history: List[Any]):
        start = state_id_or_label not in self.visited_states
        self.visited_states.add(state_id_or_label)
        state = get_state(state_id_or_label, self.state_machine)
        self.current_state = state
        if not state:
            return

        self.logger.info(f"Current State: {state}")

        await self.print_start_message(state, start=start)

        if state["type"] == "basic":
            return await self.handle_state(state["edge"], state_history + [state])

        go_to_state = lambda s, h: self.handle_state(s, h)
        speak = lambda text: self.update_history("message.bot", text)
        speak_message = lambda message: self.print_message(message)
        call_ai = lambda prompt, tool, stop=None: self.call_ai(prompt, tool, stop)

        if state["type"] == "question":
            return await handle_question(
                state=state,
                go_to_state=go_to_state,
                speak_message=speak_message,
                logger=self.logger,
                state_history=state_history
            )

        if state["type"] == "options":
            return await handle_options(
                state=state,
                go_to_state=go_to_state,
                speak=speak,
                call_ai=call_ai,
                state_machine=self.state_machine,
                get_chat_history=lambda: self.chat_history,
                logger=self.logger,
                state_history=state_history
            )

        if state["type"] == "action":
            return await self.compose_action(state, state_history)

    async def guided_response(self, guide):
        tool = {"response": "[insert your response]"}
        message = await self.call_ai(
            f"Draft your next response to the user based on the latest chat history, taking into account the following guidance:\n'{guide}'",
            tool,
        )
        self.logger.info(f"Guided response: {message}")
        message = message[message.find("{") : message.rfind("}") + 1]
        self.logger.info(f"Guided response2: {message}")
        try:
            message = parse_llm_dict(message)
            self.update_history("message.bot", message["response"])
            return message.get("response")
        except Exception as e:
            self.logger.error(f"Agent could not respond: {e}")

    async def compose_action(self, state, state_history: List[Any]):
        action = state["action"]
        next_state_history = state_history + [state]
        self.logger.info(f"Attempting to call: {action}")
        action_name = action["name"]
        action_config = self._get_action_config(action_name)
        if not action_config.starting_phrase or action_config.starting_phrase == "":
            action_config.starting_phrase = "One moment please..."
        # the value of starting_phrase is the message it says during the action
        to_say_start = action_config.starting_phrase
        # if not self.streamed and not self.agent_config.use_streaming:
        self.produce_interruptible_agent_response_event_nonblocking(
            AgentResponseMessage(message=BaseMessage(text=to_say_start))
        )
        # if we're using streaming, we need to block inputs until the tool calls are done
        self.block_inputs = True
        action_description = action["description"]
        params = action["params"]

        # We can skip instances where integrations do not need any parameters at all
        if params:
            dict_to_fill = {
                param_name: "[insert value]" for param_name in params.keys()
            }
            param_descriptions = "\n".join(
                [
                    f"'{param_name}': description: {params[param_name]['description']}, type: '{params[param_name]['type']})'"
                    for param_name in params.keys()
                ]
            )
            response = await self.call_ai(
                prompt=f"Based on the current conversation and the instructions provided, return a python dictionary with values inserted for these parameters: {param_descriptions}",
                tool=dict_to_fill,
            )
            self.logger.info(f"Filled params: {response}")
            response = response[response.find("{") : response.rfind("}") + 1]
            self.logger.info(f"Filled params: {response}")
            try:
                params = parse_llm_dict(response)
            except Exception as e:
                response = await self.call_ai(
                    prompt=f"You must return a dictionary as described. Provide the values for these parameters based on the current conversation and the instructions provided: {param_descriptions}",
                    tool=dict_to_fill,
                )
                self.logger.info(f"Filled params2: {response}")
                response = response[response.find("{") : response.rfind("}") + 1]
                params = parse_llm_dict(response)
        self.logger.info(f"Parsed params: {params}")

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
        # TODO handle if it doesnt have one

        async def run_action_and_return_input(action, action_input):
            action_output = await action.run(action_input)
            # also log the output
            pretty_function_call = (
                f"Tool Response: {action_name}, Output: {action_output}"
            )
            self.logger.info(
                f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Agent: {pretty_function_call}"
            )
            return action_input, action_output

        # accumulate the tasks so we dont wait on each one sequentially
        input, output = await run_action_and_return_input(action, action_input)
        self.block_inputs = False
        self.update_history(
            "action-finish",
            f"Action Completed: '{action_name}' completed with the following result:\ninput:'{input}'\noutput:\n{output}",
        )
        # it seems to continue on an on
        return await self.handle_state(state["edge"], next_state_history)

    #
    async def call_ai(self, prompt, tool=None, stop=None):
        stop_tokens = stop if stop is not None else []
        response_text = ""
        if not tool:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.overall_instructions},
                    {
                        "role": "user",
                        "content": f"Given the chat history, follow the instructions.\nChat history:\n{self.chat_history}\n\n\nInstructions:\n{prompt}",
                    },
                ],
                stream=True,
                temperature=0.1,
                max_tokens=500,
            )
            async for chunk in stream:
                text_chunk = chunk.choices[0].delta.content
                if text_chunk:
                    self.logger.info(f"Chunk: {chunk}")
                    response_text += text_chunk
                    if any(token in text_chunk for token in stop_tokens):
                        break
        else:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.overall_instructions},
                    {
                        "role": "user",
                        "content": f"Given the chat history, follow the instructions.\nChat history:\n{self.chat_history}\n\n\nInstructions:\n{prompt}\nYour response must always be dictionary in the following format: {str(tool)}",
                    },
                ],
                stream=True,
                temperature=0.1,
                max_tokens=500,
            )
            async for chunk in stream:
                text_chunk = chunk.choices[0].delta.content
                if text_chunk:
                    response_text += text_chunk
                    if any(token in text_chunk for token in stop_tokens):
                        break
        return response_text

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
        ]
