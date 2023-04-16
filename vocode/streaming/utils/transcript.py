import time
from typing import List
from pydantic import BaseModel, Field
from enum import Enum


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

    def add_human_message(self, text: str):
        self.messages.append(
            Message(text=text, sender=Sender.HUMAN, timestamp=time.time())
        )

    def add_bot_message(self, text: str):
        self.messages.append(
            Message(text=text, sender=Sender.BOT, timestamp=time.time())
        )
