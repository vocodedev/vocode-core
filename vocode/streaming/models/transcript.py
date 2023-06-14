import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from vocode.streaming.models.actions import ActionInput, ActionOutput
from vocode.streaming.models.events import Sender, Event, EventType

from vocode.streaming.utils.events_manager import EventsManager


class EventLog(BaseModel):
    sender: Sender
    timestamp: float

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
            return (
                f"{Sender.ACTION_WORKER.name}: {self.action_input} ({self.timestamp})"
            )
        return f"{Sender.ACTION_WORKER.name}: {self.action_input}"


class ActionFinish(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_output: ActionOutput

    def to_string(self, include_timestamp: bool = False):
        if include_timestamp:
            return (
                f"{Sender.ACTION_WORKER.name}: {self.action_output} ({self.timestamp})"
            )
        return f"{Sender.ACTION_WORKER.name}: {self.action_output}"


class Transcript(BaseModel):
    event_logs: List[EventLog] = []
    start_time: float = Field(default_factory=time.time)
    events_manager: Optional[EventsManager] = None

    class Config:
        arbitrary_types_allowed = True

    def attach_events_manager(self, events_manager: EventsManager):
        self.events_manager = events_manager

    def to_string(self, include_timestamps: bool = False) -> str:
        return "\n".join(
            event.to_string(include_timestamp=include_timestamps)
            for event in self.event_logs
        )

    def add_message(
        self,
        text: str,
        sender: Sender,
        conversation_id: str,
    ):
        timestamp = time.time()
        self.event_logs.append(Message(text=text, sender=sender, timestamp=timestamp))
        if self.events_manager is not None:
            self.events_manager.publish_event(
                TranscriptEvent(
                    text=text,
                    sender=sender,
                    timestamp=time.time(),
                    conversation_id=conversation_id,
                )
            )

    def add_human_message(self, text: str, conversation_id: str):
        self.add_message(
            text=text,
            sender=Sender.HUMAN,
            conversation_id=conversation_id,
        )

    def add_bot_message(self, text: str, conversation_id: str):
        self.add_message(
            text=text,
            sender=Sender.BOT,
            conversation_id=conversation_id,
        )

    def add_action_start_log(self, action_input: ActionInput, conversation_id: str):
        timestamp = time.time()
        self.event_logs.append(
            ActionStart(
                action_input=action_input,
                action_type=action_input.action_type,
                timestamp=timestamp,
            )
        )
        # TODO: add to event manager

    def add_action_finish_log(self, action_output: ActionOutput, conversation_id: str):
        timestamp = time.time()
        self.event_logs.append(
            ActionFinish(
                action_output=action_output,
                action_type=action_output.action_type,
                timestamp=timestamp,
            )
        )
        # TODO: add to event manager

    def update_last_bot_message_on_cut_off(self, text: str):
        # TODO: figure out what to do for the event
        for event_log in reversed(self.event_logs):
            if isinstance(event_log, Message) and event_log.sender == Sender.BOT:
                event_log.text = text
                break


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
