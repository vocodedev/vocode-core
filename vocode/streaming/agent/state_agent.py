import ast
import asyncio
import json
import logging
import re
import time
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
)

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from vocode import getenv
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneCallAction,
    VonagePhoneCallAction,
)
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponseGenerationComplete,
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
    StateAgentTranscriptActionFinish,
    StateAgentTranscriptActionInvoke,
    StateAgentTranscriptBranchDecision,
    StateAgentTranscriptDebugEntry,
    StateAgentTranscriptHandleState,
    StateAgentTranscriptInvariantViolation,
    StateAgentTranscriptMessage,
)
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import interpolate_memories
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.find_sparse_subarray import find_last_sparse_subarray


class StateMachine(BaseModel):
    states: Dict[str, Any]
    initial_state_id: str


class BranchDecision(Enum):
    PAUSE = 1
    SWITCH = 2
    CONTINUE = 3


class MemoryValue(TypedDict):
    is_ephemeral: bool
    owner_state_id: Optional[bool]
    is_stale: bool
    value: str


def parse_llm_json(s):
    if isinstance(s, dict):
        return s

    if "{" in s and "}" in s:
        s = s[s.find("{") : s.rfind("}") + 1]

    try:
        result = json.loads(s)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return {}


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
    call_ai: Callable[[str, Dict[str, Any], Optional[str], bool], Awaitable[str]],
    retry: Callable[[Optional[MemoryValue]], Awaitable[Any]],
    logger: logging.Logger,
):
    logger.info(f"handling memory dep {memory_dep}")
    # Start of Selection
    tool = {
        memory_dep["key"]: "the extracted value or 'MISSING'",
        "output": "If the information is missing, a message that asks for the missing information; else 'N/A'",
    }
    message_to_say = memory_dep["question"].get("description") or memory_dep[
        "question"
    ].get("message", "")
    logger.error(f"message_to_say |  {message_to_say}")
    output, streamed = await call_ai(
        f"""You are trying to obtain the following information: '{memory_dep['key']}'.

What it means: '{memory_dep['description'] or 'No extra details given.'}'.

Based on the user's previous responses, extract '{memory_dep['key']}' according to its description.
If the information is provided (either explicitly or implicitly), extract it.
If the information is not provided, unclear, or you cannot find it, write 'MISSING'.

Then, set 'output' as follows:
- If the information was extracted, set 'output' to 'N/A'.
- If the information is 'MISSING', generate a message that asks for '{memory_dep['key']}'.
  - Do not repeat phrases from the chat history.
  - If the user's last message was a question, answer it first before asking for '{memory_dep['key']}'.
  - If the user's last message was not a question, do not mention it.

Use the following instruction for the message: '{message_to_say}'.

Your response must be a JSON containing the keys '{memory_dep['key']}' and 'output'.""",
        tool,
        stream_output=True,
    )
    logger.error(f"memory dep output: {output}")
    output_dict = parse_llm_json(output)
    logger.info(f"mem output_dict: {output_dict}")
    memory_value = str(output_dict[memory_dep["key"]])
    message = str(output_dict["output"])
    logger.info(f"memory directly from AI: {memory_value}")
    logger.info(f"message to user: {message}")

    if memory_value != "MISSING":
        return await retry(
            {
                "is_ephemeral": memory_dep.get("is_ephemeral", False),
                "value": memory_value,
            }
        )

    await speak({"type": "verbatim", "message": message, "improvise": False}, streamed)

    async def resume(human_input: str):
        return await retry()

    return resume


async def handle_options(
    state: Any,
    go_to_state: Callable[[str], Awaitable[Any]],
    speak: Callable[[str], None],
    call_ai: Callable[[str, Dict[str, Any], Optional[str], bool], Awaitable[str]],
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
    index_to_label = (
        {}
    )  # so we can retrieve the label and pass it out for current intent description
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
        if len(edges) == 1:
            edges.append(
                {
                    "destStateId": default_next_state,
                    "aiLabel": "continue",
                    "aiDescription": "user provided an answer to the question",
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
                index_to_label[index] = edge["aiLabel"]

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
    response, streamed = await call_ai(prompt, tool, stream_output=True)

    logger.info(f"Chose condition: {response}")
    next_state_label = None
    try:
        response_dict = parse_llm_json(response)
        condition = response_dict.get("condition")
        if condition is None:
            raise ValueError("No condition was provided in the response.")
        condition = int(condition)
        next_state_id = response_to_edge[condition]["destStateId"]
        next_state_label = index_to_label[condition]
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
            output, streamed = await call_ai(prompt, tool, stream_output=True)
            output = output[output.find("{") : output.find("}") + 1]
            parsed_output = parse_llm_json(output)
            to_speak = parsed_output["response"]
            speak(to_speak)
            clarification_state = state_history[-1].copy()

            async def resume(human_input):
                logger.info(
                    f"continuing at {state['id']} with user response {human_input}"
                )
                return await go_to_state(state["id"])

            return resume, clarification_state, next_state_label
        return await go_to_state(next_state_id), None, next_state_label
    except Exception as e:
        logger.exception("Full error trace:")
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
        return await go_to_state(default_next_state), None, None


def get_default_next_state(state):
    if state["type"] != "options":
        return state["edge"]
    for edge in state["edges"]:
        if "isDefault" in edge and edge["isDefault"]:
            return edge["destStateId"]


from pydantic import BaseModel


class StateAgentState(BaseModel):
    state_machine: dict
    current_state: Optional[dict] = None
    previous_visited_states: set = set()
    memories: dict[str, MemoryValue] = {}
    can_send: bool = False
    average_latency: int = 1
    conversation_id: Optional[str] = None
    twilio_sid: Optional[str] = None
    block_inputs: bool = False
    stop: bool = False
    current_block_name: Optional[str] = None
    visited_states: set = set()
    spoken_states: set = set()
    state_history: list = []
    current_intent_description: Optional[str] = None
    chat_history: list = []
    base_url: Optional[str] = None  # maybe not important
    model: Optional[str] = None
    mark_start: bool = False
    json_transcript: Optional[StateAgentTranscript] = None
    overall_instructions: str = ""
    label_to_state_id: dict = {}
    agent_config: CommandAgentConfig


class StateAgent(RespondAgent[CommandAgentConfig]):
    def __init__(
        self,
        agent_config: CommandAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(
            agent_config=agent_config,
            logger=logger,
        )
        self.state_machine = self.agent_config.user_json_prompt["converted"]
        self.current_state = None
        self.resume_task = None
        self.resume = lambda _: self.handle_state(self.state_machine["startingStateId"])
        self.previous_resume = self.resume
        self.previous_visited_states = set()
        self.memories: dict[str, MemoryValue] = {}
        self.can_send = False
        self.average_latency = 1
        self.conversation_id = None
        self.twilio_sid = None
        self.block_inputs = False
        self.stop = False
        self.current_block_name = None
        self.visited_states = {self.state_machine["startingStateId"]}
        self.spoken_states = set()
        self.state_history = []
        self.current_intent_description = None
        self.chat_history = []
        self.base_url = getenv("AI_API_HUGE_BASE")
        self.model = self.agent_config.model_name
        self.mark_start = False
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

    @classmethod
    def from_state(
        cls, state: StateAgentState, *, logger: Optional[logging.Logger] = None
    ):
        agent = cls(agent_config=state.agent_config, logger=logger)
        agent.previous_visited_states = state.previous_visited_states
        agent.memories = state.memories
        agent.can_send = state.can_send
        agent.average_latency = state.average_latency
        agent.conversation_id = state.conversation_id
        agent.twilio_sid = state.twilio_sid
        agent.block_inputs = state.block_inputs
        agent.stop = state.stop
        agent.current_block_name = state.current_block_name
        agent.visited_states = state.visited_states
        agent.spoken_states = state.spoken_states
        agent.state_history = state.state_history
        agent.current_intent_description = state.current_intent_description
        agent.chat_history = state.chat_history
        agent.json_transcript = state.json_transcript
        agent.current_state = state.current_state
        agent.logger = logger
        agent.resume = lambda _: agent.handle_state(
            state.current_state["id"] if state and state.current_state else "start"
        )
        return agent

    def state_dump(self):
        return StateAgentState(
            **{attr: getattr(self, attr) for attr in StateAgentState.__fields__.keys()}
        )

    def cancel_stream(self):
        self.stop = True
        if (
            self.resume_task
            and not self.resume_task.done()
            and not self.resume_task.cancelled()
        ):
            self.resume_task.cancel()
            self.logger.info("Stream cancelled")

    def update_state_from_transcript(self, transcript: StateAgentTranscript):
        # Reset agent's state
        self.json_transcript = transcript
        self.chat_history = []
        self.state_history = []
        self.visited_states = set()
        self.current_state = None
        self.memories = {}
        self.block_inputs = False
        self.stop = False
        current_state_id = self.state_machine["startingStateId"]
        self.resume = lambda _: self.handle_state(self.state_machine["startingStateId"])

        # Process entries
        for entry in transcript.entries:
            if isinstance(entry, StateAgentTranscriptHandleState):
                # Update state history and current state
                state_id = entry.state_id
                state = get_state(state_id, self.state_machine)
                if state:
                    self.state_history.append(state)
                    current_state_id = state_id
                    # self.visited_states.add(state_id)
                    self.current_state = state
                    self.logger.info(
                        f"Updated state: {state.get('generated_label', state_id)}"
                    )
            elif isinstance(entry, StateAgentTranscriptMessage) and not isinstance(
                entry, AgentResponseGenerationComplete
            ):
                # Update chat history
                role = entry.role
                message = entry.message
                if role in ["human", "message.bot", "action-finish"]:
                    if role == "message.bot":
                        state_id = current_state_id
                        self.visited_states.add(state_id)
                    if len(message.strip()) > 0:
                        self.chat_history.append((role, message))
                        self.logger.info(
                            f"Added chat history entry: {role} - {message}"
                        )
            elif isinstance(entry, StateAgentTranscriptActionInvoke):
                # Handle action invocation
                action_name = entry.action_name
                self.block_inputs = True
                self.logger.info(f"Action invoked: {action_name}")
            elif isinstance(entry, StateAgentTranscriptActionFinish):
                # Handle action finish
                action_name = entry.action_name
                message = entry.message
                runtime_inputs = entry.runtime_inputs
                # Unblock inputs if they were blocked
                self.block_inputs = False
                # Update memories with runtime inputs if any
                if runtime_inputs and isinstance(runtime_inputs, dict):
                    self.memories.update(runtime_inputs)
                    self.logger.info(
                        f"Updated memories with runtime inputs: {runtime_inputs}"
                    )
                # Update chat history
                if len(message.strip()) > 0:
                    self.chat_history.append(("action-finish", message))
                    self.logger.info(f"Added action-finish to chat history: {message}")
            elif isinstance(entry, StateAgentTranscriptActionError):
                # Handle action error
                self.block_inputs = False
                self.logger.error(
                    f"Action error in transcript: {entry.raw_error_message}"
                )
            elif isinstance(entry, StateAgentTranscriptInvariantViolation):
                # Handle invariant violation
                self.logger.error(f"Invariant violation in transcript: {entry.message}")
            elif isinstance(entry, StateAgentTranscriptBranchDecision):
                # Handle branch decisions if needed
                self.logger.info(f"Branch decision made: {entry.message}")
            elif isinstance(entry, StateAgentTranscriptDebugEntry):
                # Handle debug entries if needed
                self.logger.debug(f"Debug entry: {entry.message}")
            else:
                self.logger.warning(f"Unknown entry type: {type(entry)}")

        # Update resume function based on the last state in the state_history
        if self.state_history:
            last_state = self.state_history[-1]
            # Update resume based on the type of the last state
            if last_state["type"] == "question":
                self.resume = lambda _: self.handle_state(
                    get_default_next_state(last_state)
                )
            else:
                self.resume = lambda _: self.handle_state(last_state["id"])
            self.current_state = last_state
        else:
            # Set resume to start state
            self.resume = lambda _: self.handle_state(
                self.state_machine["startingStateId"]
            )
            self.current_state = get_state(
                self.state_machine["startingStateId"], self.state_machine
            )

        self.logger.debug(
            f"Updated state from transcript. Chat history: {self.chat_history}"
        )
        self.logger.info(
            f"Current state set to: {self.current_state.get('id') if self.current_state else 'None'}"
        )
        self.logger.info(
            f"Resume function updated to state: {self.resume.__name__ if hasattr(self.resume, '__name__') else 'lambda'}"
        )

    def update_history(
        self,
        role,
        message,
        agent_response_tracker: Optional[asyncio.Event] = None,
        action_name: Optional[str] = None,
        runtime_inputs: Optional[dict] = None,
        speak: bool = True,
    ):
        if role == "human":
            while self.chat_history and self.chat_history[-1][0] == "human":
                self.chat_history.pop()
                self.json_transcript.entries.pop()
        if (
            role != "message.bot"
        ):  # we dont add it here, we add it as its said in streaming convo
            self.chat_history.append((role, message))
        if role == "action-finish":
            self.json_transcript.entries.append(
                StateAgentTranscriptActionFinish(
                    role=role,
                    message=message,
                    action_name=action_name,
                    runtime_inputs=runtime_inputs,
                )
            )
        else:
            self.json_transcript.entries.append(
                StateAgentTranscriptMessage(role=role, message=message)
            )

        if role == "message.bot" and len(message.strip()) > 0 and speak:

            self.produce_interruptible_agent_response_event_nonblocking(
                AgentResponseMessage(
                    message=BaseMessage(
                        text=interpolate_memories.interpolate_memories(
                            message, self.memories
                        )
                    )
                ),
                agent_response_tracker=agent_response_tracker,
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
        self.logger.info(
            f"current intent description: {self.current_intent_description}"
        )
        self.logger.info(f"average latency: {self.average_latency}")
        self.update_history("human", human_input)
        if self.agent_config.call_type:
            self.logger.info(
                f"[CallType.{self.agent_config.call_type.upper()}:{self.agent_config.current_call_id}] Lead:{human_input}"
            )

        transfer_block_name = self.state_machine.get("transfer_block_name")
        if (
            self.resume_task
            and not self.resume_task.cancelled()
            and not self.resume_task.done()
        ):
            self.resume_task.cancel()
            try:
                await self.resume_task
            except asyncio.CancelledError:
                self.logger.info("Old resume task cancelled")

        if transfer_block_name and self.current_block_name != transfer_block_name:
            # First analyze intent
            intent_result, streamed = await self.analyze_user_intent()
            self.logger.error(f"Intent RESULT: {intent_result}")

            if intent_result == "transfer":
                self.logger.info("Transfer condition met")
                if transfer_block_name:
                    self.resume = lambda _: self.handle_state(transfer_block_name)
                    self.previous_resume = self.resume
                    self.previous_visited_states = self.visited_states
                    self.resume_task = asyncio.create_task(self.resume(human_input))
                    await self.resume_task
                else:
                    self.logger.error("transfer_block_name not found in state_machine")
                return "", True

            elif intent_result == "switch":
                self.logger.info("Switch condition met, going to start state")
                result = await self.handle_state(
                    self.state_machine["startingStateId"],
                    trigger="switch",
                )
                self.current_intent_description = None
                return result, True

            else:  # continue or unknown intent
                self.resume_task = asyncio.create_task(self.resume(human_input))
                resume_output = await self.resume_task
                self.resume = resume_output
                return "", True

        else:
            self.logger.error("No intent task")
            self.previous_resume = self.resume
            self.previous_visited_states = self.visited_states
            if not self.resume:
                self.resume = self.previous_resume
                self.visited_states = self.previous_visited_states
                self.logger.info("Resuming from previous resume")
            self.resume_task = asyncio.create_task(self.resume(human_input))
            resume_output = await self.resume_task
            self.resume = resume_output
            return "", True

    async def print_start_message(self, state, start: bool):
        if "start_message" in state:
            if state["start_message"]["type"] != "verbatim":
                start = True
        if start and "start_message" in state:
            self.mark_start = True
            await self.print_message(state["start_message"], state["id"], is_start=True)

    async def print_message(
        self,
        message,
        current_state_id,
        is_start=False,
        memory_id=None,
        speak=True,
    ):
        if is_start:
            current_state_id = current_state_id + "_start"
        if memory_id:
            current_state_id = current_state_id + "_" + memory_id
        # I've removed automatic rephrasing of repeated verbatim messages
        # Models have trouble rephrasing transitional phrases
        if message["type"] == "verbatim":
            self.spoken_states.add(current_state_id)
            self.logger.info(
                f"Updating history with message: {message['message']} with speak {speak}"
            )
            self.update_history("message.bot", message["message"], speak=speak)
        else:
            guide = message["description"]
            await self.guided_response(guide)

    async def analyze_user_intent(self):
        last_user_message = None
        last_bot_message = None

        if len(self.state_history) <= 1:
            # We aren't already helping the user
            return "continue", False

        for role, msg in reversed(self.chat_history):
            if role == "human" and not last_user_message:
                last_user_message = msg
            elif role == "message.bot" and not last_bot_message:
                last_bot_message = msg
            if last_user_message and last_bot_message:
                break

        if not last_user_message:
            return "continue", False
        # If no intent description is set:
        # - We're almost certainly already in the start state, so no need to loop back
        # - Only allow 'transfer' or 'continue' responses ('unclear' maps to 'continue')
        # - Intent gets set to the edge's label each time we traverse an edge
        if (
            self.current_intent_description is None
            or self.current_intent_description == ""
            # if we already have the option of going to start state, this task doesn't need to worry about switching
            or self.current_block_name == "start"
        ):
            prompt = (
                f"Analyze the conversation below to classify the conversation:\n\n"
                f"Bot's last message: '{last_bot_message}'\n"
                f"User's response: '{last_user_message}'\n\n"
                f"Respond with exactly one word:\n"
                f"'transfer' - if the user asks to speak with someone else like a human, representative or operator.\n"
                f"'unclear' - if the user's intent is at all unclear or ambiguous.\n"
                f"'continue' - if the user did NOT ask to transfer."
            )
            response, streamed = await self.call_ai(prompt, stream_output=True)
            self.logger.info(f"Initial intent analysis response: {response}")
            intent = response.strip().lower()
            if intent not in ["transfer", "continue", "unclear"]:
                intent = "continue"
            if (
                intent == "unclear"
            ):  # just mimic continue behavior because memories deftly handle ambiguity already
                intent = "continue"
            return intent, streamed

        prompt = (
            f"Analyze the conversation below to classify the conversation:\n\n"
            f"Bot's last message: '{last_bot_message}'\n"
            f"User's response: '{last_user_message}'\n\n"
            f"Given the current intent: '{self.current_intent_description}', respond with exactly one word:\n"
            f"'switch' - if the user's message is unrelated to fulfillment of the current intent.\n"
            f"'transfer' - if the user asks to speak with someone else like a human, representative or operator.\n"
            f"'unclear' - if it's not clear whether the current intent is still applicable.\n"
            f"'continue' - if the user's message is related to the current intent."
        )

        response, streamed = await self.call_ai(prompt, stream_output=True)
        self.logger.info(f"Analyze user intent prompt response: {response}")
        intent = response.strip().lower()
        if intent not in ["switch", "transfer", "continue", "unclear"]:
            intent = "continue"
        if intent == "unclear":
            intent = "continue"
        self.logger.info(f"Determined user intent: {intent}")
        return intent, streamed

    async def handle_state(
        self, state_id_or_label: str, retry_count: int = 0, trigger=None
    ):
        self.logger.info(f"handle state {state_id_or_label} retry count {retry_count}")
        if state_id_or_label == "start":
            self.current_block_name = (
                "start"  # set current block name for use in allowing switch
            )
        start = (
            state_id_or_label != "start"
        )  # todo for arthur: unclear naming this regulates whether to say the starting message which is now the ending message. we dont want to say it again if we are still on the start state.
        self.visited_states.add(state_id_or_label)
        state = get_state(state_id_or_label, self.state_machine)
        # if it has a start_of_block, we are in a new block
        # set the current intent
        if "start_of_block" in state:
            self.logger.info(
                f"Starting new block, setting intent to {state.get('start_of_block')}"
            )
            self.current_intent_description = state.get("start_of_block")
        self.current_state = state

        if not state:
            self.json_transcript.entries.append(
                StateAgentTranscriptInvariantViolation(
                    message=f"state {state_id_or_label} does not exist"
                )
            )
            return
        start_of_block = state.get("start_of_block")
        if start_of_block:
            self.current_block_name = start_of_block

        self.json_transcript.entries.append(
            StateAgentTranscriptHandleState(
                state_id=state["id"],
                generated_label=state.get("generated_label", state["id"]),
                memory_dependencies=state.get("memory_dependencies"),
                memory_values=self.memories.copy(),
                trigger=trigger,
            )
        )

        self.state_history.append(state)

        if retry_count > 20:
            self.json_transcript.entries.append(
                StateAgentTranscriptInvariantViolation(
                    message=f"retried state {state['id']} too many times ({retry_count})",
                    original_state=state,
                )
            )
            await self.print_message(
                message={
                    "type": "verbatim",
                    "message": "Sorry, something went seriously wrong on my end. You can hang up, I'll have to call you back",
                },
                current_state_id=state["id"] + "_give_up",
            )
            return

        speak_message = lambda message: self.print_message(message, state["id"])
        call_ai = lambda prompt, tool=None, stop=None, stream_output=True: self.call_ai(
            prompt, tool, stop, stream_output
        )

        self.logger.info(
            f"{state['id']} memory deps: {state.get('memory_dependencies')}"
        )
        for memory_dep in state.get("memory_dependencies", []):
            cached_memory = self.memories.get(memory_dep["key"])
            self.logger.info(f"cached memory is {cached_memory}")
            if (
                cached_memory
                and cached_memory["is_ephemeral"]
                and cached_memory["owner_state_id"] != state["id"]
            ):
                cached_memory["is_stale"] = True
            if not cached_memory or cached_memory.get("is_stale") == True:

                async def retry(memory: Optional[MemoryValue] = None):
                    new_retry_count = retry_count + 1
                    if memory:
                        memory["owner_state_id"] = state["id"]
                        new_retry_count = 0
                        self.memories[memory_dep["key"]] = memory
                    return await self.handle_state(
                        state_id_or_label=state_id_or_label, retry_count=new_retry_count
                    )

                speak_message = lambda message, streamed: self.print_message(
                    message,
                    state["id"],
                    memory_id=memory_dep["key"] + "_memory",
                    speak=not streamed,
                )
                try:
                    return await handle_memory_dep(
                        memory_dep=memory_dep,
                        speak=speak_message,
                        call_ai=call_ai,
                        retry=retry,
                        logger=self.logger,
                    )
                except Exception as e:
                    logging.error("Error handling memory")
                    logging.exception("Error handling memory")
                    self.json_transcript.entries.append(
                        StateAgentTranscriptInvariantViolation(
                            message=f"error handling memory {memory_dep['key']}: {e}",
                            original_state=state,
                        )
                    )
                    return await retry()

        # Add handling for memory edges
        memory_edges = state.get("memoryEdges", [])
        if memory_edges:
            self.logger.info(f"Processing memory edges for state {state['id']}")
            memory_edge_matched = False

            for edge in memory_edges:
                memory_key = edge.get("memoryKey")
                memory_value = edge.get("memoryValue")
                dest_state_id = edge.get("destStateId")

                if memory_key and dest_state_id:
                    memory_stored_value = self.memories.get(memory_key, {}).get("value")
                    if memory_stored_value:
                        self.logger.info(
                            f"Memory key: {memory_key}, stored value: {memory_stored_value}, expected value: {memory_value}"
                        )
                        # First check for an exact match
                        if memory_stored_value == memory_value:
                            self.logger.info(
                                f"Exact match for memory key '{memory_key}'"
                            )
                            self.current_intent_description = f"Handle {memory_value}"
                            memory_edge_matched = True
                            return await self.handle_state(
                                dest_state_id, trigger="memoryEdge"
                            )
                        # Check if values match when lowercased and stripped
                        elif (
                            memory_stored_value.strip().lower()
                            == memory_value.strip().lower()
                        ):
                            self.logger.info(
                                f"Case-insensitive match for memory key '{memory_key}'"
                            )
                            self.current_intent_description = f"Handle {memory_value}"
                            memory_edge_matched = True
                            return await self.handle_state(
                                dest_state_id, trigger="memoryEdge"
                            )

            if not memory_edge_matched:
                # No match found; go to start state
                self.logger.info(f"No matching memory edge found for: {memory_key}")
                self.json_transcript.entries.append(
                    StateAgentTranscriptInvariantViolation(
                        message=f"no matching memory edge found, going to start state. State is {state}",
                        original_state=state,
                    )
                )
                return await self.handle_state(
                    self.state_machine["startingStateId"], trigger="memoryEdge-error"
                )

        await self.print_start_message(state, start=start)

        if state["type"] == "basic":

            async def resume(human_input=None):
                return await self.handle_state(state["edge"])

            stay_until_next_turn = state.get("stayUntilNextTurn", False)
            return resume if stay_until_next_turn else (await resume())

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
            # we return the next state label so we can update the intent description from inside the class
            out, clarification_state, next_state_label = await handle_options(
                state=state,
                go_to_state=go_to_state,
                speak=speak,
                call_ai=call_ai,
                state_machine=self.state_machine,
                get_chat_history=lambda: self.chat_history,
                logger=self.logger,
                state_history=self.state_history,
                append_json_transcript=append_json_transcript,
            )
            self.current_intent_description = next_state_label
            if clarification_state:
                self.state_history.append(clarification_state)
            return out

        if state["type"] == "action":
            try:
                return await self.compose_action(state)
            except Exception as e:
                logging.error(f"Error in compose_action {e}")
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

        if last_user_message:
            user_found = False
            for role, msg in self.chat_history:
                if user_found:
                    if role == "action-finish" and msg and not action_result_after_user:
                        action_result_after_user = msg
                    elif role == "message.bot" and msg and not bot_message_after_user:
                        bot_message_after_user = msg
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

        message, streamed = await self.call_ai(prompt, stream_output=True)
        message = message.strip()
        self.logger.info(f"Guided response: {message}")
        self.update_history("message.bot", message)
        return message, streamed

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

        async def saveActionResultAndMoveOn(
            action_result: str, runtime_inputs: Optional[dict] = None
        ):
            self.block_inputs = False
            self.update_history(
                role="action-finish",
                message=action_result,
                action_name=action_name,
                runtime_inputs=runtime_inputs,
            )
            # decided not to reset intent description here because it should be reset when we enter a new block
            # previous was considering resetting it here but new block behavior is more flexible
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
                    without_interpolation = param_info["description"]
                    with_interpolation = interpolate_memories.interpolate_memories(
                        without_interpolation.strip(), self.memories
                    )
                    finalized_params[param_name] = with_interpolation
                else:
                    dict_to_fill[param_name] = "[insert value]"
                    param_descriptions.append(
                        f"'{param_name}' - Description: {param_info['description']}, Type: '{param_info['type']}'"
                    )

            if dict_to_fill:
                param_descriptions_str = "\n".join(param_descriptions)
                response, streamed = await self.call_ai(
                    prompt=f"Based on the current conversation and the instructions provided, return a valid json with values inserted for these parameters:\n{param_descriptions_str}",
                    tool=dict_to_fill,
                    stream_output=True,
                )
                self.logger.info(f"Raw AI response: {response}")
                response = response[response.find("{") : response.rfind("}") + 1]
                self.logger.info(f"Extracted json: {response}")

                try:
                    ai_filled_params = eval(response)
                except Exception as e:
                    self.logger.error(
                        f"Agent did not respond with a valid json, trying to parse as JSON: {e}."
                    )
                    ai_filled_params = parse_llm_json(response)

                finalized_params.update(ai_filled_params)
        if action_name.lower() == "zapier":
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
            logging.error(f"Error in create_action {e}")
            self.json_transcript.entries.append(
                StateAgentTranscriptActionError(
                    action_name=action_name or "action has no name",
                    message=f"Failed to instantiate action. Action config was {action_config}",
                    raw_error_message=str(e),
                )
            )
            self.logger.error("Internal error in action config or not found.")
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
                logging.error(f"Error in create_action_input {e}")
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
                f"[CallType.{self.agent_config.call_type.upper()}:{self.agent_config.current_call_id}] Agent: {pretty_function_call}"
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

        runtime_inputs = None
        try:
            runtime_inputs = vars(action_input)
        except:
            pass
        # check if memories is a member of action_output
        if hasattr(output, "memories"):
            if output.memories:
                for memory_dict in output.memories:
                    key = list(memory_dict.keys())[0]
                    value = list(memory_dict.values())[0]
                    new_memory_value = MemoryValue(
                        is_ephemeral=False,
                        value=value,
                    )
                    self.memories[key] = new_memory_value
        return await saveActionResultAndMoveOn(
            action_result=f"Action Completed: '{action_name}' completed with the following result:\n{output}",
            runtime_inputs=runtime_inputs,
        )

    async def call_ai(self, prompt, tool=None, stop=None, stream_output=True):
        stop_tokens = stop if stop is not None else []
        response_text = ""
        streamed = False
        start_time = time.time()

        # Extract the last sequence of bot, user, bot messages
        last_bot_messages_before = []
        last_user_message = ""
        last_bot_messages_after = []
        user_found = False
        for role, message in reversed(self.chat_history):
            if role == "message.bot" and not user_found:
                last_bot_messages_after.insert(
                    0, message.text if isinstance(message, BaseMessage) else message
                )
            elif role == "human":
                if not user_found:
                    user_found = True
                    last_user_message = (
                        message.text if isinstance(message, BaseMessage) else message
                    )
                else:
                    break
            elif role == "message.bot" and user_found:
                last_bot_messages_before.insert(
                    0, message.text if isinstance(message, BaseMessage) else message
                )

        # Concatenate the messages
        bot_before = (
            " ".join(last_bot_messages_before).strip()
            if len(last_bot_messages_before) > 0
            else ""
        )
        last_user_message = (
            last_user_message.strip() if len(last_user_message) > 0 else ""
        )
        bot_after = (
            " ".join(last_bot_messages_after).strip()
            if len(last_bot_messages_after) > 0
            else ""
        )

        # Construct the context string
        context_parts = []
        if bot_before:
            context_parts.append(f"Bot: {bot_before}")
        if last_user_message:
            context_parts.append(f"User: {last_user_message}")
        if bot_after:
            context_parts.append(
                f"Bot: {bot_after}\n[Continue the conversation from here]"
            )

        context = (
            "Latest messages:\n" + "\n".join(context_parts) if context_parts else ""
        )
        # construct pretty printed complete history
        merged_history = []
        for role, message in self.chat_history:
            msg_text = (
                message.text if isinstance(message, BaseMessage) else str(message)
            )
            if not msg_text.strip():
                continue

            formatted_msg = f"{'Bot' if role == 'message.bot' else 'User'}: {msg_text}"

            if merged_history and merged_history[-1].startswith(
                "Bot" if role == "message.bot" else "User"
            ):
                prev_msg = merged_history[-1].split(": ", 1)[1]
                if prev_msg in msg_text:
                    merged_history[-1] = formatted_msg
                    continue

            merged_history.append(formatted_msg)

        complete_history = "\n".join(merged_history)
        # construct the memory prompt
        # it is empty if it doesn't exist
        memory_prompt = ""
        # if it does exist, it should incorporate instructions on how to use it
        saved_memories = {}
        saved_memories_str = ""
        # iterate through the dict
        for key, value in self.memories.items():
            if value and value["value"] != "MISSING" and value["is_ephemeral"] == False:
                saved_memories[key] = value
        saved_memories_str = "\n".join(
            [
                f"KEY: '{key}'\nVALUE: '{value.get('value')}'\n---"
                for key, value in saved_memories.items()
            ]
        )
        if len(saved_memories_str) > 0:
            memory_prompt = f"From the conversation so far, you've already saved some information. Memories:\n{saved_memories_str}\n\nIf instructed to interpolate a piece of information from your memories, use the exact format [[KEY]]. For example, if you want to use the value stored under 'x', write [[x]] in your response and it will be automatically replaced with the actual value."

        if not tool or tool == {}:
            prompt = f"{self.overall_instructions}\n{memory_prompt}\nGiven the recent conversation:\n{context}\n\nFollow these instructions:\n{prompt}\n\nReturn a single response."
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
            # For non-streaming, update average latency at completion
            end_time = time.time()
            if not hasattr(self, "average_latency"):
                self.average_latency = end_time - start_time
            else:
                self.average_latency = (
                    self.average_latency + (end_time - start_time)
                ) / 2  # units are in
        else:
            tool_json_str = json.dumps(tool)
            prompt = (
                f"{self.overall_instructions}\n\n"
                f"You are engaged in the following conversation:\n{complete_history}\n\n"
                "Please follow the instructions below and generate the required response.\n\n"
                f"Instructions:\n{prompt}\n"
                f"{memory_prompt}\n"
                f"Instructions:\n{prompt}\n\n"
                f"The latest exchange was as follows:\n{context}\n\n"
                f"Your response must always be a json in the following format: {tool_json_str}.\n"
                "Return only the json, without any additional commentary."
            )
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
            buffer = ""
            output_started = False
            json_key = '"output": '
            punctuation = [".", "!", "?", ",", ";"]
            send_final_message = False
            first_chunk = True
            first_response_sent = False
            async for chunk in stream:
                await asyncio.sleep(0)
                text_chunk = chunk.choices[0].delta.content
                if text_chunk:
                    response_text += text_chunk
                    buffer += text_chunk
                    if not output_started:
                        idx = buffer.find(json_key)
                        if idx != -1:
                            output_started = True
                            value_start = idx + len(json_key)
                            buffer = buffer[value_start:]
                    elif (
                        stream_output and "MISSING" in response_text
                    ):  # only want to say the output if its missing

                        while any(p in buffer for p in punctuation):
                            split_index = max(
                                buffer.rfind(p) for p in punctuation if p in buffer
                            )
                            content = buffer[: split_index + 1]
                            buffer = buffer[split_index + 1 :]
                            if (
                                content.strip()
                                and content.strip() != '"}'
                                and content.strip() != "}"
                            ):
                                # if its the first chunk and the first character is a double quote, remove it
                                if first_chunk and content.strip().startswith('"'):
                                    first_chunk = False
                                    content = content.strip()[1:]
                                interpolated_content = (
                                    interpolate_memories.interpolate_memories(
                                        content.strip(), self.memories
                                    )
                                )
                                self.logger.info(
                                    f"streaming content. Raw: {content}  interpolated: {interpolated_content}"
                                )
                                self.produce_interruptible_agent_response_event_nonblocking(
                                    AgentResponseMessage(
                                        message=BaseMessage(text=interpolated_content)
                                    )
                                )
                                if not first_response_sent:
                                    # Update average latency on first response for streaming
                                    end_time = time.time()
                                    if not hasattr(self, "average_latency"):
                                        self.average_latency = end_time - start_time
                                    else:
                                        self.average_latency = (
                                            self.average_latency
                                            + (end_time - start_time)
                                        ) / 2
                                    first_response_sent = True
                                streamed = True
                                send_final_message = True
                    if any(token in text_chunk for token in stop_tokens):
                        break
            if (
                buffer.strip()
                and send_final_message
                and buffer.strip() != '"}'
                and buffer.strip() != "}"
            ):
                # if there is just one double quote in the whole thing, remove it
                if buffer.strip().count('"') == 1:
                    buffer = buffer.replace('"', "")
                interpolated_content = interpolate_memories.interpolate_memories(
                    buffer.strip(), self.memories
                )
                self.logger.info(
                    f"Streaming final message. Raw: {buffer}  interpolated: {interpolated_content}"
                )
                self.produce_interruptible_agent_response_event_nonblocking(
                    AgentResponseMessage(message=BaseMessage(text=interpolated_content))
                )
                if not first_response_sent:
                    # Update average latency if we haven't sent any responses yet
                    end_time = time.time()
                    if not hasattr(self, "average_latency"):
                        self.average_latency = end_time - start_time
                    else:
                        self.average_latency = (
                            self.average_latency + (end_time - start_time)
                        ) / 2
                streamed = True
        return (
            interpolate_memories.interpolate_memories(response_text, self.memories),
            streamed,
        )

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
