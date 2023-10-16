import time
from typing import List, Optional, Tuple, Any

from pydantic import BaseModel, Field

from vocode.streaming.models.actions import ActionInput, ActionOutput
from vocode.streaming.models.events import ActionEvent, Sender, Event, EventType
from vocode.streaming.utils.events_manager import EventsManager


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
    current_start_index: int = 0

    class Config:
        arbitrary_types_allowed = True

    def update_dialog_state(self, new_dialog_state: Any):
        if self.current_dialog_state is not None:
            # Push the current belief state to the history before updating it
            self.dialog_states_history.append(
                BeliefStateEntry(
                    belief_state=self.current_dialog_state,
                    start_message_index=self.current_start_index,
                    end_message_index=len(self.event_logs) - 1,  # Index of the last message
                )
            )
        # Update current belief state and start index
        self.current_dialog_state = new_dialog_state
        self.current_start_index = len(self.event_logs)  # Next message starts a new range

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

    @property
    def last_user_message(self) -> Optional[str]:
        user_messages = self.user_messages
        if len(user_messages) == 0:
            return None
        return user_messages[-1].text

    @property
    def last_assistant(self) -> Optional[str]:
        assistant_messages = []
        found_human = False

        # Gets last sequence of Bot messages.
        for log in reversed(self.event_logs):
            if log.sender == Sender.BOT and not found_human:
                assistant_messages.append(log.text)
            elif log.sender == Sender.HUMAN:
                found_human = True
                if assistant_messages:
                    break

        if assistant_messages:
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
        # TODO: this is duplicate with to_string but kept for compatibility with vocode. Later only one should stay.
        conversation_str = ""
        print(include_belief_state, len(self.dialog_states_history))
        last_end_index = -1  # So we know when a new belief state range starts

        for log in self.event_logs:
            conversation_str += f"{log.timestamp} {log.sender}: {log.text}\n"
            if include_belief_state:
                current_index = self.event_logs.index(log)

                # Check if this log index is the start of a new belief state range
                if current_index == self.current_start_index and current_index > last_end_index:
                    conversation_str += f"Now using new belief state:\n{self.current_dialog_state.dict()}\n"
                    last_end_index = current_index  # Update last_end_index to avoid repeating prints

                for entry in self.dialog_states_history:
                    if entry.start_message_index == current_index and current_index > last_end_index:
                        conversation_str += f"Now using new belief state:\n{entry.belief_state.dict()}\n"
                        last_end_index = current_index  # Update last_end_index to avoid repeating prints

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
