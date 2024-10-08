import asyncio
import json
import logging
import re
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from vocode import getenv
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneCallAction,
    VonagePhoneCallAction,
)
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponseMessage,
    RespondAgent,
)
from vocode.streaming.agent.utils import translate_message
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.models.agent import CommandAgentConfig
from vocode.streaming.models.call_type import CallType
from vocode.streaming.models.events import Sender
from vocode.streaming.models.memory_dependency import MemoryDependency
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.state_agent_transcript import (
    StateAgentTranscript,
    StateAgentTranscriptActionError,
    StateAgentTranscriptActionInvoke,
    StateAgentTranscriptBranchDecision,
    StateAgentTranscriptDebugEntry,
    StateAgentTranscriptHandleState,
    StateAgentTranscriptInvariantViolation,
    StateAgentTranscriptMessage,
)
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.find_sparse_subarray import find_last_sparse_subarray


class StateMachine(BaseModel):
    states: Dict[str, Any]
    initial_state_id: str


class BranchDecision(Enum):
    PAUSE = 1
    SWITCH = 2
    CONTINUE = 3


def parse_llm_dict(s):
    if isinstance(s, dict):
        return s
    # Extract everything between and including the first and last curly braces
    if "{" in s and "}" in s:
        s = s[s.find("{") : s.rfind("}") + 1]
    s = s.replace("\n{", "{")
    s = s.replace("{\n", "{")
    s = s.replace("\n}", "}")
    s = s.replace("}\n", "}")
    s = (
        s.replace('"', "'")
        .replace("\n", "<newline>")
        .replace("  ", " ")
        .replace("','", "', '")
    )
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
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            result[key] = value

    # If the result is empty, try parsing as a single key-value pair
    if not result:
        match = re.match(r"\s*{\s*'?(\w+)'?\s*:\s*'?([^']+)'?\s*}\s*", s)
        if match:
            key, value = match.groups()
            if value.isdigit():
                value = int(value)
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
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
    go_to_state: Callable[[str], Awaitable[Any]],
    speak_message: Callable[[Any], None],
    logger: logging.Logger,
    state_history: List[Any],
):

    await speak_message(state["question"])

    async def resume(human_input):
        logger.info(f"continuing at {state['id']} with user response {human_input}")
        return await go_to_state(get_default_next_state(state))

    return resume


async def handle_memory_dep(
    memory_dep: MemoryDependency,
    speak: Callable[[dict], Awaitable[None]],
    call_ai: Callable[[str, Dict[str, Any], Optional[str]], Awaitable[str]],
    retry: Callable[[Optional[str]], Awaitable[Any]],
    logger: logging.Logger,
):
    logger.info(f"handling memory dep {memory_dep}")
    tool = {
        memory_dep[
            "key"
        ]: "the value provided by the human, or MISSING if it's not available"
    }
    output = await call_ai(
        f"Based solely on the provided chat history between a human and a bot, extract the following information:\n{memory_dep['key']}\n\nInformation Description:\n{memory_dep['description'] or 'No further description provided.'}\n\nIf it's not provided by the human in the conversation, set the value to MISSING.",
        tool,
    )
    output_dict = parse_llm_dict(output[output.find("{") : output.find("}") + 1])
    logger.error(f"mem output_dict: {output_dict}")
    memory = output_dict[memory_dep["key"]]
    logger.info(f"memory directly from AI: {memory}")
    if memory != "MISSING":
        return await retry(memory)

    await speak(memory_dep["question"])

    async def resume(human_input: str):
        return await retry()

    return resume


async def handle_options(
    state: Any,
    go_to_state: Callable[[str], Awaitable[Any]],
    speak: Callable[[str], None],
    call_ai: Callable[[str, Dict[str, Any], Optional[str]], Awaitable[str]],
    state_machine: Any,
    get_chat_history: Callable[[], List[Tuple[str, str]]],
    logger: logging.Logger,
    state_history: List[Any],
    append_json_transcript: Callable[[StateAgentTranscriptDebugEntry], None],
):
    last_user_message_index = None
    last_user_message = None
    last_bot_message = state_machine["states"]["start"]["start_message"]["message"]
    truly_last_bot_message = None
    action_result_after_user_spoke = None
    next_state_history = state_history + [state]

    for i, (role, msg) in enumerate(reversed(get_chat_history())):
        if last_user_message_index is None and role == "human" and msg:
            last_user_message_index = len(get_chat_history()) - i - 1
            last_user_message = msg
            break

    if last_user_message_index is not None:
        for i, (role, msg) in enumerate(
            reversed(get_chat_history()[:last_user_message_index])
        ):
            if role == "message.bot" and msg:
                last_bot_message = msg
                break

    if last_user_message_index:
        for i, (role, msg) in enumerate(
            get_chat_history()[last_user_message_index + 1 :]
        ):
            if role == "action-finish" and msg:
                action_result_after_user_spoke = msg
                break

    for role, msg in reversed(get_chat_history()):
        if role == "message.bot" and msg:
            truly_last_bot_message = msg
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

    if (
        state["id"] != state_machine["startingStateId"]
        and (
            prev_state
            and "question"
            in prev_state.get("generated_label", prev_state["id"]).lower()
        )
        and not action_result_after_user_spoke
    ):
        if len(edges) > 0:
            if edges[-1].get("aiDescription"):
                edges[-1]["aiDescription"] = (
                    f'{edges[-1]["aiDescription"]}\n\nOnly pick the following options if none of '
                    f"the above options can be applied to the current circumstance:"
                )
            else:
                edges[-1]["aiLabel"] = (
                    f'{edges[-1]["aiLabel"]}\n\nOnly pick the following options if none of the '
                    f"above options can be applied to the current circumstance:"
                )
        edges.append(
            {
                "destStateId": state_machine["startingStateId"],
                "aiLabel": "switch",
                "aiDescription": f"user no longer needs help with '{state['id'].split('::')[0]}'",
            }
        )
        if (
            len(edges) == 1
        ):  # this gets added if there is only one condition so we can gracefully handle moving forward
            edges.append(
                {
                    "destStateId": default_next_state,
                    "aiLabel": "continue",
                    "aiDescription": f"user provided an answer to the question",  # TODO: it seems to repeat the state on this
                }
            )
        else:
            edges.append(
                {
                    "destStateId": default_next_state,
                    "aiLabel": "continue",
                    "aiDescription": f"user still needs help with '{state['id'].split('::')[0]}' but no condition applies",
                }
            )
        if "question" in state.get("generated_label", state["id"]).split("::")[-2]:
            edges.append(
                {
                    "destStateId": default_next_state,
                    "speak": True,
                    "aiLabel": "question",
                    "aiDescription": "user seems confused or unsure",
                },
            )

    index = 0
    for index, edge in enumerate(edges):
        if "isDefault" not in edge or not edge["isDefault"]:
            response_to_edge[index] = edge
            if edge.get("aiLabel"):
                response_to_edge[edge["aiLabel"]] = edge

            ai_options.append(
                f"{index}: {edge.get('aiDescription', None) or edge.get('aiLabel', None)}"
            )

    ai_options_str = "\n".join(ai_options)
    prompt = (
        f"Bot's last statement: '{last_bot_message}'\n"
        f"User's response: '{last_user_message}'\n"
        f"{'Last tool output: ' + action_result_after_user_spoke if action_result_after_user_spoke else ''}\n\n"
        "Identify the number associated with the most fitting condition from the list below:\n"
        f"{ai_options_str}\n\n"
        "Always return a number from the above list. Return the number of the condition that best applies."
    )
    if truly_last_bot_message:
        prompt = (
            f"Bot's last statement: '{last_bot_message}'\n"
            f"User's response: '{last_user_message}'\n"
            f"{'Last tool output: ' + action_result_after_user_spoke if action_result_after_user_spoke else ''}\n\n"
            f"Bot is thinking: '{truly_last_bot_message}'\n"
            "Identify the number associated with the most fitting condition from the list below:\n"
            f"{ai_options_str}\n\n"
            "Always return a number from the above list. Return the number of the condition that best applies."
        )
    # logger.info(f"AI prompt constructed: {prompt}")
    response = await call_ai(
        prompt,
        tool,
    )

    logger.info(f"Chose condition: {response}")
    try:
        response_dict = parse_llm_dict(response)
        condition = response_dict.get("condition")
        if condition is None:
            raise ValueError("No condition was provided in the response.")
        condition = int(condition)
        next_state_id = response_to_edge[condition][
            "destStateId"
        ]  # this gets set as start if user is confused and the default next is start
        append_json_transcript(
            StateAgentTranscriptBranchDecision(
                message=f"branching to {next_state_id}",
                ai_prompt=prompt,
                ai_tool=tool,
                ai_response=response,
                internal_edges=edges,
                original_state=state,
            )
        )
        # the issue is that start has no start message
        if response_to_edge[condition].get("speak"):
            tool = {"response": "insert your response to the user"}
            prompt = (
                f"You last stated: '{last_bot_message}', to which the user replied: '{last_user_message}'.\n\n"
                f"You are already engaged in the following process: {state['id'].split('::')[0]}\n"
                "Right now, you are pausing the process to assist the confused user.\n"
                "Respond as follows: If the user didn't answer, politely restate the question and ask for a clear answer.\n"
                "- If the user asked a question, provide a concise answer and then ask for a clear answer if you are waiting for one.\n"
                "- Ensure not to suggest any actions or offer alternatives.\n"
            )
            # todo, if current state is an options state which it is shouldnt we repeat it instead of moving forward
            output = await call_ai(prompt, tool)
            output = output[output.find("{") : output.find("}") + 1]
            parsed_output = parse_llm_dict(output)
            to_speak = parsed_output["response"]
            speak(to_speak)
            clarification_state = state_history[
                -1
            ].copy()  # we want to copy the last question state

            async def resume(human_input):
                logger.info(
                    f"continuing at {state['id']} with user response {human_input}"
                )
                return await go_to_state(state["id"])

            return resume, clarification_state
        return await go_to_state(next_state_id), None
    except Exception as e:
        append_json_transcript(
            StateAgentTranscriptInvariantViolation(
                message="error evaluating ai response",
                extra_info={
                    "ai_prompt": prompt,
                    "ai_tool": tool,
                    "ai_response": response,
                    "internal_edges": edges,
                },
                original_state=state,
            )
        )
        logger.error(f"Agent chose no condition: {e}. Response was {response}")
        return await go_to_state(default_next_state), None


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
        self.resume_task = None
        self.resume = lambda _: self.handle_state(self.state_machine["startingStateId"])
        self.memories = {}
        self.can_send = False
        self.conversation_id = None
        self.twilio_sid = None
        self.block_inputs = False
        self.stop = False
        self.visited_states = {self.state_machine["startingStateId"]}
        self.spoken_states = set()
        self.state_history = []
        self.chat_history = [("message.bot", self.agent_config.initial_message)]
        self.base_url = getenv("AI_API_HUGE_BASE")
        self.model = self.agent_config.model_name
        self.client = AsyncOpenAI(
            base_url=self.base_url,
        )
        self.json_transcript = StateAgentTranscript()

        self.overall_instructions = (
            self.agent_config.prompt_preamble
            + "\n"
            + self.state_machine["states"]["start"]["instructions"]
        )
        self.label_to_state_id = self.state_machine["labelToStateId"]

    def update_state_from_transcript(self, transcript: StateAgentTranscript):
        self.json_transcript = transcript
        self.chat_history = []
        self.state_history = []
        self.visited_states = set()
        self.current_state = None

        for entry in transcript.entries:
            type_of_entry = type(entry)
            self.logger.info(f"Type of entry: {type_of_entry}")
            if isinstance(entry, StateAgentTranscriptHandleState):
                state_id = entry.state_id
                state = get_state(state_id, self.state_machine)
                if state:
                    self.state_history.append(state)
                    self.visited_states.add(state_id)
                    self.current_state = state
                    self.logger.info(
                        f"Updated state: {state.get('generated_label', state_id)}"
                    )
                    # Set resume immediately after updating the state
                    if state["type"] == "question":
                        self.resume = lambda _: self.handle_state(
                            get_default_next_state(state)
                        )
                    else:
                        self.resume = lambda _: self.handle_state(state["id"])
            elif isinstance(entry, StateAgentTranscriptMessage):
                role = entry.role
                message = entry.message
                if role in [
                    "human",
                    "message.bot",
                    "action-finish",
                ]:
                    if len(message.strip()) > 0:
                        self.chat_history.append((role, message))
                        self.logger.info(
                            f"Added chat history entry: {role} - {message}"
                        )

            elif isinstance(entry, StateAgentTranscriptActionInvoke):
                self.logger.info(f"Action invoked: {entry}")
            elif isinstance(entry, StateAgentTranscriptActionError):
                self.logger.error(
                    f"Action error in transcript: {entry.raw_error_message}"
                )
            elif isinstance(entry, StateAgentTranscriptInvariantViolation):
                self.logger.error(f"Invariant violation in transcript: {entry.message}")
            else:
                self.logger.warning(f"Unknown entry type: {type(entry)}")

        # If no states were processed, set resume to the starting state
        if not self.state_history:
            self.resume = lambda _: self.handle_state(
                self.state_machine["startingStateId"]
            )

        self.logger.debug(
            f"Updated state from transcript. Chat history: {self.chat_history}"
        )
        self.logger.info(
            f"Resume function updated to state: {self.resume.__name__ if hasattr(self.resume, '__name__') else 'lambda'}"
        )

    def update_history(self, role, message):
        if role == "human":
            # Remove the last human message if it exists
            while self.chat_history and self.chat_history[-1][0] == "human":
                self.chat_history.pop()
                self.json_transcript.entries.pop()

        self.chat_history.append((role, message))
        self.json_transcript.entries.append(
            StateAgentTranscriptMessage(role=role, message=message)
        )

        if role == "message.bot" and len(message.strip()) > 0:
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=message))
            )

    def get_json_transcript(self):
        return self.json_transcript

    def get_latest_bot_message(self):
        for role, message in reversed(self.chat_history):
            if isinstance(message, BaseMessage):
                if role == "message.bot" and len(message.text.strip()) > 0:
                    return message.text
            else:
                return message
        return "How can I assist you today?"

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
        if (
            self.resume_task
            and not self.resume_task.cancelled()
            and not self.resume_task.done()
        ):  # if something in progress, we want to move back when cancelling
            self.resume_task.cancel()
            # self.move_back_state()
            try:
                await self.resume_task
            except asyncio.CancelledError:
                self.logger.info(f"Old resume task cancelled")

        self.resume_task = asyncio.create_task(self.resume(human_input))
        resume_output = await self.resume_task
        if self.resume_task.cancelled():
            resume_output = self.resume
        self.resume = resume_output
        self.block_inputs = False
        return "", True

    async def print_start_message(self, state, start: bool):
        if "start_message" in state:
            if state["start_message"]["type"] != "verbatim":
                start = True  # no need to skip the print if its relative since it wont be repetitive
        if start and "start_message" in state:
            await self.print_message(
                state["start_message"], state["id"], is_start=True
            )  # doesn't print the start message if it's a repeat

    async def print_message(
        self, message, current_state_id, is_start=False, memory_id=None
    ):

        if is_start:
            current_state_id = (
                current_state_id + "_start"
            )  # so that we separately keep track of the start message
        if memory_id:
            current_state_id = current_state_id + "_" + memory_id
        if current_state_id in self.spoken_states and message["type"] == "verbatim":
            original_message = message["message"]
            constructed_guide = f"You previously communicated to the user: '{original_message}'. If this was a question, the user's response might have been unclear. Address their query (if any) and tactfully seek the information you need. If it was a statement, rephrase it using different words while maintaining its core meaning, tone and approximate length."
            await self.guided_response(constructed_guide)
        else:
            if message["type"] == "verbatim":
                self.spoken_states.add(current_state_id)
                self.update_history("message.bot", message["message"])
            else:
                guide = message["description"]
                await self.guided_response(guide)
        if not self.agent_config.allow_interruptions:
            # sleep for 1
            await asyncio.sleep(0.5)
            self.block_inputs = True

    async def handle_state(self, state_id_or_label: str):
        start = state_id_or_label not in self.visited_states
        self.visited_states.add(state_id_or_label)
        state = get_state(state_id_or_label, self.state_machine)
        self.current_state = state

        if not state:
            self.json_transcript.entries.append(
                StateAgentTranscriptInvariantViolation(
                    message=f"state {state_id_or_label} does not exist"
                )
            )
            return
        self.json_transcript.entries.append(
            # use the ID as label if label not available, like if the agent was last updated before labels existed
            StateAgentTranscriptHandleState(
                state_id=state["id"],
                generated_label=state.get("generated_label", state["id"]),
                memory_dependencies=state.get("memory_dependencies"),
                memory_values=self.memories,
            )
        )

        self.state_history.append(state)
        # self.logger.info(f"Current State: {state}")
        speak_message = lambda message: self.print_message(message, state["id"])
        call_ai = lambda prompt, tool=None, stop=None: self.call_ai(prompt, tool, stop)

        self.logger.info(
            f"{state['id']} memory deps: {state.get('memory_dependencies')}"
        )
        for memory_dep in state.get("memory_dependencies", []):
            cached_memory = self.memories.get(memory_dep["key"])
            self.logger.info(f"cached memory is {cached_memory}")
            if not cached_memory:

                async def retry(memory: Optional[str] = None):
                    if memory:
                        self.memories[memory_dep["key"]] = memory
                    return await self.handle_state(state_id_or_label=state_id_or_label)

                speak_message = lambda message: self.print_message(
                    message, state["id"], memory_id=memory_dep["key"] + "_memory"
                )
                return await handle_memory_dep(
                    memory_dep=memory_dep,
                    speak=speak_message,
                    call_ai=call_ai,
                    retry=retry,
                    logger=self.logger,
                )

        await self.print_start_message(state, start=start)

        if state["type"] == "basic":
            return await self.handle_state(state["edge"])

        go_to_state = lambda s: self.handle_state(s)
        speak = lambda text: self.update_history("message.bot", text)

        if state["type"] == "question":
            return await handle_question(
                state=state,
                go_to_state=go_to_state,
                speak_message=speak_message,
                logger=self.logger,
                state_history=self.state_history,
            )

        def append_json_transcript(m: StateAgentTranscriptDebugEntry):
            self.json_transcript.entries.append(m)

        if state["type"] == "options":
            out, clarification_state = await handle_options(
                state=state,
                go_to_state=go_to_state,
                speak=speak,
                call_ai=call_ai,
                state_machine=self.state_machine,
                get_chat_history=lambda: self.chat_history,
                logger=self.logger,
                state_history=self.state_history,
                append_json_transcript=append_json_transcript
            )
            if clarification_state:
                self.state_history.append(clarification_state)
            return out

        if state["type"] == "action":
            try:
                return await self.compose_action(state)
            except Exception as e:
                # invariant violation, not action error, because compose_action is supposed to do it's own error handling
                self.json_transcript.entries.append(
                    StateAgentTranscriptInvariantViolation(
                        message=f"uncaught exception in compose_action: {e}",
                        original_state=state,
                    )
                )

    async def guided_response(self, guide):
        last_user_message = None
        last_bot_message_before_user = None
        action_result_after_user = None
        bot_message_after_user = None

        # Find the last user message and the last bot message before it
        for role, msg in reversed(self.chat_history):
            if role == "human" and msg and not last_user_message:
                last_user_message = msg
            elif (
                role == "message.bot"
                and msg
                and not last_bot_message_before_user
                and last_user_message
            ):
                last_bot_message_before_user = msg
                break

        # Find action result and bot message after user message
        if last_user_message:
            user_found = False
            for role, msg in self.chat_history:
                if user_found:
                    if role == "action-finish" and msg and not action_result_after_user:
                        action_result_after_user = msg
                    elif role == "message.bot" and msg and not bot_message_after_user:
                        bot_message_after_user = msg
                        break
                elif msg == last_user_message:
                    user_found = True

        prompt = (
            f"Draft a single response to the user based on the latest chat history, taking into account the following guidance:\n'{guide}'\n\n"
            f"Bot's last statement before user: '{last_bot_message_before_user}'\n"
            f"User's response: '{last_user_message}'\n"
        )
        if action_result_after_user:
            prompt += f"Last tool output: {action_result_after_user}\n"
        if bot_message_after_user:
            prompt += f"Bot's is thinking: '{bot_message_after_user}'\n"
        prompt += "\nNow, respond as the BOT directly."

        message = await self.call_ai(prompt, None)
        message = message.strip()
        self.logger.info(f"Guided response: {message}")
        self.update_history("message.bot", message)
        return message

    async def compose_action(self, state):
        action = state["action"]
        self.json_transcript.entries.append(
            StateAgentTranscriptActionInvoke(
                state_id=state["id"],
                action_name=action.get("name", "action has no name"),
            )
        )
        self.state_history.append(state)
        self.logger.info(f"Attempting to call: {action}")
        action_name = action["name"]
        action_description = action["description"]
        self.logger.debug(f"Action description: {action_description}")

        async def saveActionResultAndMoveOn(action_result: str):
            self.block_inputs = False
            self.update_history("action-finish", action_result)
            return await self.handle_state(state["edge"])

        try:
            action_config = self._get_action_config(action_name)
            if not action_config.starting_phrase or action_config.starting_phrase == "":
                action_config.starting_phrase = "One moment please..."
            to_say_start = action_config.starting_phrase
            if len(to_say_start.strip()) > 0:
                self.produce_interruptible_agent_response_event_nonblocking(
                    AgentResponseMessage(message=BaseMessage(text=to_say_start))
                )
        except Exception as e:
            self.logger.error(
                f"Action config not found. Simulating action completion. Error: {e}"
            )
            to_say_start = "One moment please..."
            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=to_say_start))
            )
            return await saveActionResultAndMoveOn(
                action_result=f"Action Completed: Demo Action, {action_name}, was simulated successfully."
            )
        params = None
        if "params" in action:
            params = action["params"]
        finalized_params = {}

        if params:
            dict_to_fill = {}
            param_descriptions = []
            for param_name, param_info in params.items():
                fill_type = param_info.get("fill_type")
                if fill_type == "exact":
                    finalized_params[param_name] = param_info["description"]
                else:
                    dict_to_fill[param_name] = "[insert value]"
                    param_descriptions.append(
                        f"'{param_name}' - Description: {param_info['description']}, Type: '{param_info['type']}'"
                    )

            if dict_to_fill:
                param_descriptions_str = "\n".join(param_descriptions)
                response = await self.call_ai(
                    prompt=f"Based on the current conversation and the instructions provided, return a python dictionary with values inserted for these parameters:\n{param_descriptions_str}",
                    tool=dict_to_fill,
                )
                self.logger.info(f"Raw AI response: {response}")
                response = response[response.find("{") : response.rfind("}") + 1]
                self.logger.info(f"Extracted dictionary: {response}")

                try:
                    ai_filled_params = eval(response)
                except Exception as e:
                    self.logger.error(
                        f"Agent did not respond with a valid dictionary, trying to parse as JSON: {e}."
                    )
                    ai_filled_params = parse_llm_dict(response)

                finalized_params.update(ai_filled_params)
        if action_name.lower() == "zapier":
            # is the action description
            if action_description:
                params = {
                    "zapier_name": action_description,
                    "params": finalized_params,
                }
            else:
                self.logger.error(
                    f"Action description not found for action {action_name}"
                )
                return await saveActionResultAndMoveOn(
                    action_result=f"action {action_name} failed to run due missing action description"
                )
        elif action_name.lower() == "run_python":
            # remove the code from the params
            code = finalized_params.pop("code")
            params = {
                "code": code,
                "params": finalized_params,
            }
        else:
            params = finalized_params

        self.logger.info(f"Final params for action {action_name}: {params}")

        try:
            action = self.action_factory.create_action(action_config)
        except Exception as e:
            self.json_transcript.entries.append(
                StateAgentTranscriptActionError(
                    action_name=action_name or "action has no name",
                    message=f"Failed to instantiate action. Action config was {action_config}",
                    raw_error_message=str(e),
                )
            )
            self.logger.error(f"Internal error in action config or not found.")
            return await saveActionResultAndMoveOn(
                action_result=f"action {action_name} failed to run due to an internal error"
            )

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
            try:
                action_input = action.create_action_input(
                    conversation_id=self.conversation_id,
                    params=params,
                    user_message_tracker=None,
                )
            except Exception as e:
                self.json_transcript.entries.append(
                    StateAgentTranscriptActionError(
                        action_name=action_name or "an action has no name",
                        message=f"Failed to instantiate action input. Params were {params}",
                        raw_error_message=str(e),
                    )
                )
                return await saveActionResultAndMoveOn(
                    action_result=f"action {action_name} failed to run due to an internal error"
                )

        async def run_action_and_return_input(action, action_input):
            action_output = await action.run(action_input)
            pretty_function_call = (
                f"Tool Response: {action_name}, Output: {action_output}"
            )
            self.logger.info(
                f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Agent: {pretty_function_call}"
            )
            return action_input, action_output

        input = action_input
        output = "Action failed to run"
        self.block_inputs = True
        try:
            input, output = await run_action_and_return_input(action, action_input)
        except Exception as e:
            self.logger.error(f"Action failed to run. Error: {str(e)}")
            self.json_transcript.entries.append(
                StateAgentTranscriptActionError(
                    action_name=action_name,
                    message=f"Failed to run action. Raw input was {action_input}",
                    raw_error_message=str(e),
                )
            )

        return await saveActionResultAndMoveOn(
            f"Action Completed: '{action_name}' completed with the following result:\ninput:'{input}'\noutput:\n{output}"
        )

    async def call_ai(self, prompt, tool=None, stop=None):
        stop_tokens = stop if stop is not None else []
        # stop_tokens.append("}")
        response_text = ""
        pretty_chat_history = "\n".join(
            [
                f"{'Bot' if role == 'message.bot' else 'Human'}: {message.text if isinstance(message, BaseMessage) else message}"
                for role, message in self.chat_history
                if (isinstance(message, BaseMessage) and len(message.text) > 0)
                or (not isinstance(message, BaseMessage) and len(str(message)) > 0)
            ]
        )
        if not tool or tool == {}:
            prompt = f"{self.overall_instructions}\n\n Given the chat history, follow the instructions.\nChat history:\n{pretty_chat_history}\n\n\nInstructions:\n{prompt}\n\nReturn a single response."
            # self.logger.debug(f"prompt is: {prompt}")
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                stream=True,
                temperature=0.1,
                max_tokens=4000,
            )
            async for chunk in stream:
                text_chunk = chunk.choices[0].delta.content
                if text_chunk:
                    response_text += text_chunk
                    if any(token in text_chunk for token in stop_tokens):
                        break
        else:
            prompt = f"Given the chat history, follow the instructions.\nChat history:\n{pretty_chat_history}\n\n\nInstructions:\n{prompt}\nYour response must always be dictionary in the following format: {str(tool)}. Return just the dictionary without any additional commentary."
            self.logger.debug(f"prompt is: {prompt}")

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.overall_instructions},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                temperature=0.1,
                max_tokens=4000,
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

        functions = []
        for action_config in self.agent_config.actions:
            if action_config is not None:
                action = self.action_factory.create_action(action_config)
                if action is not None:
                    functions.append(action.get_openai_function())
        return functions

    def move_back_state(self):
        # Remove the current state
        if self.state_history:
            self.state_history.pop()

        # Find the last question state
        while self.state_history:
            previous_state = self.state_history[-1]
            if previous_state["type"] == "question":
                break
            else:
                self.state_history.pop()

        # Merge consecutive messages of the same role
        merged_messages = []
        for role, message in self.chat_history:
            current_message = (
                message.text if isinstance(message, BaseMessage) else message
            )
            if merged_messages and merged_messages[-1][0] == role:
                last_message = merged_messages[-1][1]
                if isinstance(last_message, BaseMessage):
                    merged_messages[-1] = (
                        role,
                        BaseMessage(text=f"{last_message.text} {current_message}"),
                    )
                else:
                    merged_messages[-1] = (role, f"{last_message} {current_message}")
            else:
                if isinstance(message, BaseMessage):
                    merged_messages.append((role, BaseMessage(text=current_message)))
                else:
                    merged_messages.append((role, current_message))

        # Log the merged messages for debugging
        self.logger.info(f"Merged messages: {merged_messages}")
        self.chat_history = merged_messages
        # self.chat_history = list(reversed(merged_messages))
        # Remove everything after the second to latest bot message and replace the second to latest with the removed latest
        bot_messages = [
            i
            for i, (role, _) in enumerate(merged_messages)
            if role == "bot"  # try with bot message
        ]
        if len(bot_messages) >= 2:
            second_last_user_index = bot_messages[-2]
            last_user_index = bot_messages[-1]
            merged_messages[second_last_user_index] = merged_messages[last_user_index]
            self.chat_history = merged_messages[: second_last_user_index + 1]
        else:
            self.chat_history = merged_messages
        merged_messages = []
        for role, message in self.chat_history:
            current_message = (
                message.text if isinstance(message, BaseMessage) else message
            )
            if merged_messages and merged_messages[-1][0] == role:
                last_message = merged_messages[-1][1]
                if isinstance(last_message, BaseMessage):
                    merged_messages[-1] = (
                        role,
                        BaseMessage(text=f"{last_message.text} {current_message}"),
                    )
                else:
                    merged_messages[-1] = (role, f"{last_message} {current_message}")
            else:
                if isinstance(message, BaseMessage):
                    merged_messages.append((role, BaseMessage(text=current_message)))
                else:
                    merged_messages.append((role, current_message))

        self.chat_history = merged_messages
        # if the last message is a user message and there are consecutive user messages before it that are contained in the last user message, remove the consecutive before ones
        if self.chat_history[-1][0] == "human":
            # go backwards
            for i in range(len(self.chat_history) - 2, -1, -1):
                if (
                    self.chat_history[i][0] == "human"
                    and self.chat_history[i][1].text in self.chat_history[-1][1].text
                ):
                    self.chat_history = self.chat_history[: i + 1]
                    break
                else:
                    break

        # Set the resume state
        if self.state_history:
            self.resume = lambda _: self.handle_state(self.state_history[-1]["id"])
        else:
            self.resume = lambda _: self.handle_state(
                self.state_machine["startingStateId"]
            )

    # this might not be needed.
    def restore_resume_state(self):
        if self.state_history:
            current_state = self.state_history[-1]
            if "edge" in current_state:
                self.resume = lambda _: self.handle_state(current_state["edge"])
            elif "edges" in current_state:
                for state in current_state["edges"]:
                    if "isDefault" in state and state["isDefault"]:
                        self.resume = lambda _: self.handle_state(state["destStateId"])
                        return
                self.resume = lambda _: self.handle_state(current_state[id])
            else:
                self.resume = lambda _: self.handle_state("start")
