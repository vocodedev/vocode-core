import time
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from vocode.streaming.models.events import Sender, Event, EventType

from vocode.streaming.utils.events_manager import EventsManager


class Message(BaseModel):
    text: str
    sender: Sender
    timestamp: float
    metadata: dict = {}

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


class Transcript(BaseModel):
    messages: List[Message] = []
    start_time: float = Field(default_factory=time.time)

    def to_string(self, include_timestamps: bool = False) -> str:
        return "\n".join(
            message.to_string(include_timestamp=include_timestamps)
            for message in self.messages
        )

    def add_message(
        self,
        text: str,
        sender: Sender,
        events_manager: EventsManager,
        conversation_id: str,
        metadata: Optional[dict] = None,
    ):
        timestamp = time.time()
        self.messages.append(Message(text=text, sender=sender, timestamp=timestamp, metadata=metadata or {}))
        events_manager.publish_event(
            TranscriptEvent(
                text=text,
                sender=sender,
                timestamp=time.time(),
                conversation_id=conversation_id,
                metadata=metadata,
            )
        )

    def add_human_message(
        self, text: str, events_manager: EventsManager, conversation_id: str, metadata: Optional[dict] = None
    ):
        self.add_message(
            text=text,
            sender=Sender.HUMAN,
            events_manager=events_manager,
            conversation_id=conversation_id,
            metadata=metadata,
        )

    def add_bot_message(
        self, text: str, events_manager: EventsManager, conversation_id: str, metadata: Optional[dict] = None
    ):
        self.add_message(
            text=text,
            sender=Sender.BOT,
            events_manager=events_manager,
            conversation_id=conversation_id,
            metadata=metadata,
        )


class TranscriptEvent(Event, type=EventType.TRANSCRIPT):
    text: str
    sender: Sender
    timestamp: float
    metadata: dict = {}

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


class TranscriptCompleteEvent(Event, type=EventType.TRANSCRIPT_COMPLETE):
    transcript: Transcript
