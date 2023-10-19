import json
import time
from copy import copy
from typing import List, Optional, Tuple, Any, Dict

from pydantic import BaseModel, Field

from vocode.streaming.models.actions import ActionInput, ActionOutput
from vocode.streaming.models.events import ActionEvent, Sender, Event, EventType
from vocode.streaming.utils.events_manager import EventsManager

SENDER_TO_OPENAI_ROLE = {Sender.HUMAN: 'user', Sender.BOT: 'assistant'}


class EventLog(BaseModel):
    sender: Sender
    timestamp: float = Field(default_factory=time.time)

    def to_string(self, include_timestamp: bool = False) -> str:
        raise NotImplementedError


class Message(EventLog):
    text: str

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


class ActionStart(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_input: ActionInput

    def to_string(self, include_timestamp: bool = False):
        if include_timestamp:
            return f"{Sender.ACTION_WORKER.name}: params={self.action_input.params.dict()} ({self.timestamp})"
        return f"{Sender.ACTION_WORKER.name}: params={self.action_input.params.dict()}"


class ActionFinish(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_output: ActionOutput

    def to_string(self, include_timestamp: bool = False):
        if include_timestamp:
            return f"{Sender.ACTION_WORKER.name}: action_type='{self.action_type}' response={self.action_output.response.dict()} ({self.timestamp})"
        return f"{Sender.ACTION_WORKER.name}: action_type='{self.action_type}' response={self.action_output.response.dict()}"


class Summary(BaseModel):
    text: str
    timestamp: float = Field(default_factory=time.time)
    last_message_ind: int

    def to_string(self, include_timestamp: bool = False) -> str:
        return f"{self.text}"


class BeliefStateEntry(BaseModel):
    belief_state: Any
    decision: Optional[Any]

    start_message_index: int
    end_message_index: int

    timestamp: float = Field(default_factory=time.time)


class Transcript(BaseModel):
    event_logs: List[EventLog] = []
    start_time: float = Field(default_factory=time.time)
    events_manager: Optional[EventsManager] = None
    summaries: Optional[List[Summary]] = None

    dialog_states_history: List[BeliefStateEntry] = []
    current_dialog_state: Optional[Any] = None
    current_start_index: int = -1

    class Config:
        arbitrary_types_allowed = True

    def log_dialog_state(self, new_dialog_state: Any, decision: Optional[Any] = None):
        if self.current_dialog_state is not None:
            # Push the current belief state to the history before updating it
            self.dialog_states_history.append(
                BeliefStateEntry(
                    belief_state=self.current_dialog_state.copy(),
                    decision=copy(decision),
                    start_message_index=self.current_start_index,
                    end_message_index=len(self.event_logs) - 1,  # Index of the last message before the new state
                )
            )
        # Update current belief state and start index
        self.current_dialog_state = new_dialog_state.copy()
        self.current_start_index = len(self.event_logs)  # Next message starts a new range

    def _calculate_diff(self, previous_state: Any, new_state: Any) -> Dict:
        diff = {}
        previous_state_dict = previous_state.dict()
        new_state_dict = new_state.dict()
        for key, value in new_state_dict.items():
            if key not in previous_state_dict or previous_state_dict[key] != value:
                diff[key] = value
        return diff

    @property
    def num_messages(self):
        return len(self.event_logs)

    @property
    def last_message(self) -> Optional[EventLog]:
        if self.num_messages == 0:
            return None
        return self.event_logs[-1]

    @property
    def user_messages(self) -> List[Message]:
        return [message for message in self.event_logs if message.sender == Sender.HUMAN]

    @property
    def assistant_messages(self) -> List[Message]:
        return [message for message in self.event_logs if message.sender == Sender.BOT]

    def get_message_history(self):
        return [{"role": SENDER_TO_OPENAI_ROLE[log.sender], "content": log.text}
                # all messages except for system message
                for log in self.event_logs if log.sender in (Sender.BOT, Sender.HUMAN)]

    @property
    def last_user_message(self) -> Optional[str]:
        user_messages = self.user_messages
        if len(user_messages) == 0:
            return None
        return user_messages[-1].text

    @property
    def last_assistant(self) -> Optional[str]:
        assistant_messages = []
        temp_messages = []

        # Iterate through each event log entry, reversed
        for log in reversed(self.event_logs):
            if log.sender == Sender.BOT:
                # If the sender is the bot, append message to the temporary list
                temp_messages.append(log.text)
            elif log.sender == Sender.HUMAN and temp_messages:
                # If the sender is human and there are messages in the temporary list,
                # assign the temporary list to the main list and clear the temporary list
                assistant_messages = temp_messages.copy()
                temp_messages = []
            # If there are no bot messages after a human message, just continue

        # If there were no human messages after the last sequence of bot messages,
        # assign the temp messages to assistant_messages
        if temp_messages:
            assistant_messages = temp_messages

        if assistant_messages:
            # Join the messages into a single string, maintaining original order
            return " ".join(reversed(assistant_messages))

        return None

    @property
    def last_summary_message_ind(self) -> Optional[int]:
        if self.summaries is None or len(self.summaries) == 0:
            return None
        return self.summaries[-1].last_message_ind

    @property
    def num_summaries(self):
        if self.summaries is None:
            return 0
        return len(self.summaries)

    @property
    def last_summary(self) -> Optional[Summary]:
        if self.summaries is None or len(self.summaries) == 0:
            return None
        return self.summaries[-1]

    def summary_data(self) -> Tuple[str, Optional[str]]:
        transcript = self.to_string() if self.summaries is None else self.to_string_from(
            self.summaries[-1].last_message_ind)
        previous_summary = self.last_summary
        previous_summary_text = previous_summary.text if previous_summary is not None else None

        return transcript, previous_summary_text

    def attach_events_manager(self, events_manager: EventsManager):
        self.events_manager = events_manager

    def to_string(self, include_timestamps: bool = False) -> str:
        return "\n".join(
            event.to_string(include_timestamp=include_timestamps)
            for event in self.event_logs
        )

    def to_string_from(self, index: int, include_timestamps: bool = False) -> str:
        """Return a string representation of the transcript from a given index."""
        return "\n".join(
            event.to_string(include_timestamp=include_timestamps)
            for event in self.event_logs[index:]
        )

    def maybe_publish_transcript_event_from_message(
            self, message: Message, conversation_id: str
    ):
        if self.events_manager is not None:
            self.events_manager.publish_event(
                TranscriptEvent(
                    text=message.text,
                    sender=message.sender,
                    timestamp=message.timestamp,
                    conversation_id=conversation_id,
                )
            )

    def add_message_from_props(
            self,
            text: str,
            sender: Sender,
            conversation_id: str,
            publish_to_events_manager: bool = True,
    ):
        timestamp = time.time()
        message = Message(text=text, sender=sender, timestamp=timestamp)
        self.event_logs.append(message)
        if publish_to_events_manager:
            self.maybe_publish_transcript_event_from_message(
                message=message, conversation_id=conversation_id
            )

    def add_message(
            self,
            message: Message,
            conversation_id: str,
            publish_to_events_manager: bool = True,
    ):
        self.event_logs.append(message)
        if publish_to_events_manager:
            self.maybe_publish_transcript_event_from_message(
                message=message, conversation_id=conversation_id
            )

    def add_human_message(self, text: str, conversation_id: str):
        self.add_message_from_props(
            text=text,
            sender=Sender.HUMAN,
            conversation_id=conversation_id,
        )

    def add_summary(self, text: str):

        timestamp = time.time()
        summary = Summary(
            text=text,
            timestamp=timestamp,
            last_message_ind=self.num_messages
        )
        if self.summaries is None:
            self.summaries = [summary]
            return
        # FIXME: avoid adding duplicate summaries for example self.num_message == self.last_summary_message_ind
        self.summaries.append(
            summary
        )

    def add_bot_message(self, text: str, conversation_id: str):
        self.add_message_from_props(
            text=text,
            sender=Sender.BOT,
            conversation_id=conversation_id,
        )

    def get_last_user_message(self):
        for idx, message in enumerate(self.event_logs[::-1]):
            if message.sender == Sender.HUMAN:
                return -1 * (idx + 1), message.to_string()

    def get_last_bot_message(self):
        for idx, message in enumerate(self.event_logs[::-1]):
            if message.sender == Sender.BOT:
                return -1 * (idx + 1), message.to_string()

    def add_action_start_log(self, action_input: ActionInput, conversation_id: str):
        timestamp = time.time()
        self.event_logs.append(
            ActionStart(
                action_input=action_input,
                action_type=action_input.action_config.type,
                timestamp=timestamp,
            )
        )
        if self.events_manager is not None:
            self.events_manager.publish_event(
                ActionEvent(
                    action_input=action_input.dict(),
                    conversation_id=conversation_id,
                )
            )

    def add_action_finish_log(
            self,
            action_input: ActionInput,
            action_output: ActionOutput,
            conversation_id: str,
    ):
        timestamp = time.time()
        self.event_logs.append(
            ActionFinish(
                action_output=action_output,
                action_type=action_output.action_type,
                timestamp=timestamp,
            )
        )
        if self.events_manager is not None:
            self.events_manager.publish_event(
                ActionEvent(
                    action_input=action_input.dict(),
                    action_output=action_output.dict(),
                    conversation_id=conversation_id,
                )
            )

    def update_last_bot_message_on_cut_off(self, text: str):
        # TODO: figure out what to do for the event
        for event_log in reversed(self.event_logs):
            if isinstance(event_log, Message) and event_log.sender == Sender.BOT:
                event_log.text = text
                break

    def render_conversation(self, include_belief_state: bool = False) -> str:
        conversation_str = ""
        current_entry_index = 0

        # Initial belief state before any messages if it's available and included
        if include_belief_state and self.dialog_states_history:
            first_entry = self.dialog_states_history[0]
            conversation_str += f"Initial belief state:\n{json.dumps(first_entry.belief_state.dict(), indent=4, sort_keys=True)}\n"
            if first_entry.decision:
                conversation_str += f"Initial decision made:\n{first_entry.decision}\n"

        for log_index, log in enumerate(self.event_logs):
            print(log_index, current_entry_index)
            if include_belief_state:
                if current_entry_index < len(self.dialog_states_history):
                    print("IN", current_entry_index)
                    current_entry = self.dialog_states_history[current_entry_index]

                    if log_index > current_entry.end_message_index:
                        print("Log ingex", log_index, "current entry", current_entry.end_message_index)
                        current_entry_index += 1
                        if current_entry_index < len(self.dialog_states_history):
                            next_entry = self.dialog_states_history[current_entry_index]

                            conversation_str += f"Now using new belief state:\n{json.dumps(next_entry.belief_state.dict(), indent=4, sort_keys=True)}\n"
                            if next_entry.decision:
                                conversation_str += f"Decision made:\n{next_entry.decision}\n"

                            diff = self._calculate_diff(current_entry.belief_state, next_entry.belief_state)
                            if diff:
                                conversation_str += f"Differences with previous state:\n{json.dumps(diff, indent=4, sort_keys=True)}\n"

                elif self.current_dialog_state is not None and (
                        not self.dialog_states_history or log_index > self.dialog_states_history[-1].end_message_index):
                    print(self.dialog_states_history[-1].end_message_index, log_index)
                    conversation_str += f"Now using new belief state:\n{json.dumps(self.current_dialog_state.dict(), indent=4, sort_keys=True)}\n"
                    if hasattr(self.current_dialog_state, 'decision') and self.current_dialog_state.decision:
                        conversation_str += f"Current decision made:\n{self.current_dialog_state.decision}\n"

            conversation_str += f"{log.timestamp} {log.sender}: {log.text}\n"

        return conversation_str


class TranscriptEvent(Event, type=EventType.TRANSCRIPT):
    text: str
    sender: Sender
    timestamp: float

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


class TranscriptCompleteEvent(Event, type=EventType.TRANSCRIPT_COMPLETE):
    transcript: Transcript
