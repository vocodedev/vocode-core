import json
import logging
import re
import asyncio
import time
from typing import Any, Dict, List, Optional

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

class StateMachine(BaseModel):
    states: Dict[str, Any]
    initial_state_id: str


class StateAgent(RespondAgent[CommandAgentConfig]):
    def __init__(
        self,
        agent_config: CommandAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)
        self.state_machine = self.agent_config.user_json_prompt["converted"]
        self.current_state = None
        self.resume = None
        self.can_send = False
        self.conversation_id = None
        self.twilio_sid = None
        self.block_inputs = False  # independent of interruptions, actions cannot be interrupted when a starting phrase is present
        self.stop = False
        self.chat_history = []
        if "medusa" in self.agent_config.model_name.lower():
            self.base_url = getenv("AI_API_HUGE_BASE")
            self.model = getenv("AI_MODEL_NAME_HUGE")
        else:
            self.base_url = getenv("AI_API_BASE")
            self.model = getenv("AI_MODEL_NAME_LARGE")
        # self.client = AsyncOpenAI(
        #     base_url=self.base_url,
        #     api_key="<HF_API_TOKEN>",  # replace with your token
        # )
        self.logger.info(f"Hellpo")  # I left off with it not parsing the state machien

        self.logger.info(f"State machine: {self.state_machine}")
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
        human_input: Optional[str] = None,
        is_interrupt: bool = False,
        stream_output: bool = True,
    ):
        if human_input:
            self.update_history("human", human_input)
            if self.agent_config.language != "en-US":
                translated_message = translate_message(
                    self.logger,
                    human_input,
                    self.agent_config.language,
                    "en-US",
                )
                self.logger.info(
                    f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Lead:{human_input}"
                )
                human_input = translated_message
            elif self.agent_config.language == "en-US":
                self.logger.info(
                    f"[{self.agent_config.call_type}:{self.agent_config.current_call_id}] Lead:{human_input}"
                )

            last_bot_message = next(
                (
                    msg[1]
                    for msg in reversed(self.chat_history)
                    if msg[0] == "message.bot" and msg[1] and len(msg[1].strip()) > 0
                ),
                "",
            )
            move_on = await self.maybe_respond_to_user(last_bot_message, human_input)
            if not move_on:
                # self.update_history("message.bot", last_bot_message)
                return (
                    "",
                    True,
                )  # TODO: it repeats itself here, if maybe ends up saying something, no need to say it here with update
        if self.resume and human_input:
            await self.resume(human_input)
        elif not self.resume and not human_input:
            self.resume = await self.handle_state("start", True)
        elif not self.resume:
            self.resume = await self.choose_block(state=self.current_state)
        return "", True

    async def print_start_message(self, state):
        self.logger.info(f"Current State: {state}")
        if "start_message" in state:
            start_message = state["start_message"]
            if start_message["type"] == "verbatim":
                self.update_history("message.bot", start_message["message"])
            else:
                guide = start_message["description"]
                await self.guided_response(guide)

    async def handle_state(self, state_id, start=False):
        self.update_history("debug", f"STATE IS {state_id}")
        if not state_id:
            return
        state = self.state_machine["states"][state_id]
        self.current_state = state

        if state["type"] == "crossroads":

            async def resume(human_input):
                self.resume = None
                return await self.choose_block(state=state)

            if start:
                await self.print_start_message(state)
                return resume
            else:
                return await resume("")

        await self.print_start_message(state)

        if state["type"] == "basic":
            return await self.handle_state(state["edge"])

        if state["type"] == "question":
            question = state["question"]
            if question["type"] == "verbatim":
                self.update_history("message.bot", question["message"])
            else:
                await self.guided_response(question["description"])

            async def resume(answer):
                self.update_history(
                    "debug", f"continuing at {state_id} with user response {answer}"
                )
                return await self.handle_state(state["edge"])

            return resume

        if state["type"] == "condition":
            return await self.condition_check(state=state)

        if state["type"] == "action":
            return await self.compose_action(state)

    async def guided_response(self, guide):
        self.update_history("debug", f"Running guided response with guide: {guide}")
        tool = {"response": "[insert your response]"}
        message = await self.call_ai(
            "Draft your next response to the user based on the latest chat history, taking into account the following guidance:\n'{guide}'",
            tool,
        )
        message = message[message.find("{") : message.rfind("}") + 1]
        message = eval(message)
        self.update_history("message.bot", message["response"])

    async def choose_block(self, state=None, choose_from=None):
        if state is None:
            states = self.state_machine["states"][
                self.state_machine["startingStateId"]
            ]["edges"]
        else:
            if "edges" in state:
                states = state["edges"]
            else:
                states = [state["edge"]]
        # if choose_from is set, we will let it choose from all available
        # aadd choose_from to the states list
        if choose_from:
            states += (
                choose_from
                + self.state_machine["states"][self.state_machine["startingStateId"]][
                    "edges"
                ]
            )
        if len(states) == 1:
            next_state_id = states[0]
            return await self.handle_state(next_state_id)
        # split each on the :: and get the first element, then remove duplicates
        states = list(set([s.split("::")[0] for s in states]))
        numbered_states = "\n".join([f"{i + 1}. {s}" for i, s in enumerate(states)])
        self.logger.info(f"Numbered states: {numbered_states}")
        streamed_choice = await self.call_ai(
            f"Choose from the available states:\n{numbered_states}\nReturn just a single number corresponding to your choice."
        )
        match = re.search(r"\d+", streamed_choice)
        chosen_int = int(match.group()) if match else 1
        next_state_id = states[chosen_int - 1]
        next_state_id = self.label_to_state_id[next_state_id]
        self.update_history("debug", f"The bot chose {chosen_int}, aka {next_state_id}")
        self.logger.info(f"Chose {next_state_id}")
        return await self.handle_state(next_state_id)

    async def condition_check(self, state):
        self.update_history("debug", "Running condition check")
        choices = "\n".join(
            [f"'{c}'" for c in state["condition"]["conditionToStateLabel"].keys()]
        )
        self.update_history("debug", f"Choices: {choices}")
        tool = {"condition": "[insert the condition that applies]"}
        choices = "\n".join(
            [f"- '{c}'" for c in state["condition"]["conditionToStateLabel"].keys()]
        )
        self.logger.info(f"Choosing condition from:\n{choices}")
        # check if there is more than one condition
        if len(state["condition"]["conditionToStateLabel"]) > 1:
            response = await self.call_ai(
                f"{state['condition']['prompt']}. Conditions:\n{choices}\nGiven the provided context and the current state of the conversation, return the condition that applies. If none of the conditions apply, return 'none'.",
                tool,
            )
        else:  # with just a single condition, change the prompt
            single_condition = list(state["condition"]["conditionToStateLabel"].keys())[
                0
            ]
            response = await self.call_ai(
                f"{state['condition']['prompt']} Given the current state of the conversation, is the condition '{single_condition}' applicable? If so, return the condition name. If not applicable, return 'none'.",
                tool,
            )
        response = response[response.find("{") : response.rfind("}") + 1]
        self.logger.info(f"Chose condition: {response}")
        response = eval(response)
        for condition, next_state_label in state["condition"][
            "conditionToStateLabel"
        ].items():
            if condition == response["condition"]:
                next_state_id = self.label_to_state_id[next_state_label]
                return await self.handle_state(next_state_id)
            else:
                self.update_history(
                    "debug", f"condition {condition} != response {response}"
                )
        return await self.handle_state(state["edge"])

    async def compose_action(self, state):
        action = state["action"]
        self.logger.info(f"Attempting to call: {action}")
        action_name = action["name"]
        action_description = action["description"]
        params = action["params"]
        dict_to_fill = {param_name: "[insert value]" for param_name in params.keys()}
        param_descriptions = "\n".join(
            [
                f"'{param_name}': description: {params[param_name]['description']}, type: '{params[param_name]['type']})'"
                for param_name in params.keys()
            ]
        )
        response = await self.call_ai(
            f"Based on the instructions and current conversational context, please provide values for the following parameters: {param_descriptions}",
            dict_to_fill,
        )
        response = response[response.find("{") : response.rfind("}") + 1]
        self.logger.info(f"Filled params: {response}")
        params = eval(response)
        action_config = self._get_action_config(action_name)

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
        if not action_config.starting_phrase or action_config.starting_phrase == "":
            action_config.starting_phrase = "Starting action..."
        # the value of starting_phrase is the message it says during the action
        self.update_history(
            "action-start",
            f"Running action {action_name} with params response {response}",
        )
        to_say_start = action_config.starting_phrase
        # if not self.streamed and not self.agent_config.use_streaming:
        self.produce_interruptible_agent_response_event_nonblocking(
            AgentResponseMessage(message=BaseMessage(text=to_say_start))
        )
        # if we're using streaming, we need to block inputs until the tool calls are done
        self.block_inputs = True

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
        # TODO: HERE we need to actually run it
        self.update_history(
            "action-finish",
            f"Action '{action_name}' with input '{input}' completed with result: {output}",
        )
        # it seems to continue on an on
        if state["edge"] == "start":
            self.current_state = None
            self.resume = None  # its continuing on so im trying to reset resume
            return {}
        else:
            return await self.handle_state(state["edge"])

    async def maybe_respond_to_user(self, question, user_response):
        continue_tool = {
            "[either 'PAUSE' or 'CONTINUE' or 'SWITCH']": "[insert your response to the user]",
        }
        if self.current_state and self.current_state["id"]:
            current_workflow = self.current_state["id"].split("::")[0]
        else:
            current_workflow = "start of conversation"
        prompt = (
            f"You last stated: '{question}', to which the user replied: '{user_response}'.\n\n"
            f"You're in the process of helping the user with: {current_workflow}\n"
            "To best assist the user, decide whether you should:\n"
            "- 'CONTINUE' the process to the next step\n"
            "- 'PAUSE' the current process to obtain a clear answer from the user\n"
            "- 'SWITCH' to a different process if the user wants to do something else."
        )
        self.logger.info(f"Prompt: {prompt}")
        # we do not care what it has to say when switching or continuing
        output = await self.call_ai(prompt, continue_tool, stop=["CONTINUE", "SWITCH"])
        self.logger.info(f"Output: {output}")
        if "CONTINUE" in output:
            return True
        if "SWITCH" in output:

            def get_states_from_block():
                if self.current_state and self.current_state["id"]:
                    latest_state_id = self.current_state["id"].split("::")[0]
                    # iterates through all available states
                    block_states = []
                    for state_id, state in self.state_machine["states"].items():
                        current_state_id = state["id"].split("::")[0]
                        if current_state_id == latest_state_id:
                            block_states.append(state_id)
                    return block_states
                else:
                    return []

            self.resume = await self.choose_block(
                state=self.current_state, choose_from=get_states_from_block()
            )

            # self.update_history("message.bot", question)
            return False
        output = output[output.find("{") : output.rfind("}") + 1]
        output = eval(output.replace("'None'", "'none'").replace("None", "'none'"))
        if "PAUSE" in output:
            self.update_history("message.bot", output["PAUSE"])
            return False
        self.logger.info(f"falling back with {output}")
        return True

    async def call_ai(self, prompt, tool=None, stop=None):
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="<HF_API_TOKEN>",  # replace with your token
        )
        if not tool:
            self.update_history("message.instruction", prompt)
            # return input(f"[message.bot] $: ")
            chat_completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.overall_instructions},
                    {
                        "role": "user",
                        "content": f"Given the chat history, follow the instructions.\nChat history:\n{self.chat_history}\nInstructions:\n{prompt}",
                    },
                ],
                stream=False,
                stop=stop if stop is not None else [],
                max_tokens=500,
            )
            return chat_completion.choices[0].message.content
        else:
            self.update_history("message.instruction", prompt)
            chat_completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.overall_instructions},
                    {
                        "role": "user",
                        "content": f"Given the chat history, follow the instructions.\nChat history:\n{self.chat_history}\nInstructions:\n{prompt}\nRespond with a dictionary in the following format: {tool}",
                    },
                ],
                stream=False,
                stop=stop if stop is not None else [],
                max_tokens=500,
            )
            return chat_completion.choices[0].message.content

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
        ]
