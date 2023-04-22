import time
from typing import List
from pydantic import BaseModel, Field
from enum import Enum
from vocode.streaming.models.events import TranscriptEvent

from vocode.streaming.utils.events_manager import EventsManager


class Sender(str, Enum):
    HUMAN = "human"
    BOT = "bot"


class Message(BaseModel):
    text: str
    sender: Sender
    timestamp: float

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

    def add_message(self, text: str, sender: Sender, events_manager: EventsManager, conversation_id: str):
        timestamp = time.time()
        self.messages.append(
            Message(text=text, sender=sender, timestamp=timestamp)
        )
        events_manager.publish_event(
            TranscriptEvent(
                text=text,
                sender=Sender.HUMAN,
                timestamp=time.time(),
                conversation_id=conversation_id,
            )
        )


    def add_human_message(self, text: str, events_manager: EventsManager, conversation_id: str):
        self.add_message(text=text, sender=Sender.HUMAN, events_manager=events_manager, conversation_id=conversation_id)

    def add_bot_message(self, text: str, events_manager: EventsManager, conversation_id: str):
        self.add_message(text=text, sender=Sender.BOT, events_manager=events_manager, conversation_id=conversation_id)
