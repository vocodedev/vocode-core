import time
from datetime import datetime
from typing import List, Literal, Optional

from pydantic.v1 import BaseModel, Field

from vocode.streaming.models.actions import ActionInput, ActionOutput
from vocode.streaming.models.events import ActionEvent, Event, EventType, Sender
from vocode.streaming.utils.events_manager import EventsManager


class EventLog(BaseModel):
    sender: Sender
    timestamp: float = Field(default_factory=time.time)

    def to_string(self, include_timestamp: bool = False) -> str:
        raise NotImplementedError

    def get_timestamp_string(self, start_timestamp: float) -> str:
        dt = datetime.fromtimestamp(self.timestamp - start_timestamp)
        return f"[{dt.strftime('%M:%S')}.{dt.microsecond // 10000:02}]"


class Message(EventLog):
    text: str
    is_final: bool = False
    is_backchannel: bool = False
    is_end_of_turn: bool = False

    def to_string(
        self,
        include_timestamp: bool = False,
        mark_human_backchannels_with_brackets: bool = False,
        include_sender: bool = True,
    ) -> str:
        text = self.text
        if not self.is_final and self.sender == Sender.BOT:
            text = f"{text}-"
        if self.is_backchannel and mark_human_backchannels_with_brackets:
            text = f"[{text}]"
        if include_timestamp:
            return f"{self.sender.name}: {text} ({self.timestamp})"
        elif include_sender:
            return f"{self.sender.name}: {text}"
        else:
            return text


class ActionStart(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_input: ActionInput

    def to_string(self, include_timestamp: bool = False, include_header: bool = True):
        main_string = self.action_input.action_config.action_attempt_to_string(self.action_input)
        if include_header:
            main_string = f"BOT_ACTION_START: {main_string}"
        if include_timestamp:
            return f"{main_string} ({self.timestamp})"
        return main_string


class ActionFinish(EventLog):
    sender: Sender = Sender.ACTION_WORKER
    action_type: str
    action_input: ActionInput
    action_output: ActionOutput

    def to_string(self, include_timestamp: bool = False, include_header: bool = True):
        main_string = self.action_input.action_config.action_result_to_string(
            self.action_input, self.action_output
        )
        if include_header:
            main_string = f"BOT_ACTION_FINISH: {main_string}"
        if include_timestamp:
            return f"{main_string} ({self.timestamp})"
        return main_string


ConferenceEventType = Literal[
    "participant_joined", "participant_left", "participant_unanswered", "voicemail"
]
ConferenceEventRole = Literal["primary", "transfer"]


class ConferenceEvent(EventLog):
    sender: Sender = Sender.CONFERENCE
    conference_event_type: ConferenceEventType
    conference_event_role: ConferenceEventRole
    participant_phone_number: str

    def to_string(self, include_timestamp: bool = False, include_sender: bool = True):
        if (
            self.conference_event_type == "participant_unanswered"
            or self.conference_event_type == "voicemail"
        ):
            msg_string = f"{self.conference_event_role.capitalize()} number ({self.participant_phone_number}) did not join the conference because they are busy"
        else:
            verb = "joined" if self.conference_event_type == "participant_joined" else "left"
            msg_string = f"{self.conference_event_role.capitalize()} number ({self.participant_phone_number}) {verb} the conference"
        if include_sender:
            msg_string = f"CONFERENCE_EVENT: {msg_string}"
        if include_timestamp:
            return f"{msg_string} ({self.timestamp})"
        return msg_string


class TranscriptEvent(Event, type=EventType.TRANSCRIPT):  # type: ignore
    text: str
    sender: Sender
    timestamp: float

    def to_string(self, include_timestamp: bool = False) -> str:
        if include_timestamp:
            return f"{self.sender.name}: {self.text} ({self.timestamp})"
        return f"{self.sender.name}: {self.text}"


class Transcript(BaseModel):
    event_logs: List[EventLog] = []
    start_time: float = Field(default_factory=time.time)
    events_manager: Optional[EventsManager] = None

    class Config:
        arbitrary_types_allowed = True

    def to_string(
        self, include_timestamps: bool = False, mark_human_backchannels_with_brackets: bool = False
    ) -> str:
        event_strings = []
        for event in self.event_logs:
            if isinstance(event, Message):
                event_string = event.to_string(
                    include_timestamp=False,
                    mark_human_backchannels_with_brackets=mark_human_backchannels_with_brackets,
                )
            else:
                event_string = event.to_string(include_timestamp=False)

            if include_timestamps:
                event_string = f"{event.get_timestamp_string(self.start_time)} {event_string}"
            event_strings.append(event_string)

        return "\n".join(event_strings)

    def attach_events_manager(self, events_manager: EventsManager):
        self.events_manager = events_manager

    def maybe_publish_transcript_event_from_message(self, message: Message, conversation_id: str):
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
        is_final: bool = False,
        is_backchannel: bool = False,
        publish_to_events_manager: bool = True,
    ):
        timestamp = time.time()
        message = Message(
            text=text,
            sender=sender,
            timestamp=timestamp,
            is_final=is_final,
            is_backchannel=is_backchannel,
        )
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

    def add_human_message(self, text: str, conversation_id: str, is_backchannel: bool = False):
        self.add_message_from_props(
            text=text,
            sender=Sender.HUMAN,
            conversation_id=conversation_id,
            is_backchannel=is_backchannel,
        )

    def add_bot_message(self, text: str, conversation_id: str, is_final: bool = False):
        self.add_message_from_props(
            text=text,
            sender=Sender.BOT,
            conversation_id=conversation_id,
            is_final=is_final,
        )

    def get_last_user_message(self):
        for idx, message in enumerate(self.event_logs[::-1]):
            if message.sender == Sender.HUMAN:
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
                action_input=action_input,
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

    def was_last_message_interrupted(self):
        bot_messages = [
            message
            for message in self.event_logs
            if isinstance(message, Message) and message.sender == Sender.BOT
        ]
        if len(bot_messages) > 0:
            last_bot_message = bot_messages[-1]
            return not last_bot_message.is_final or not last_bot_message.is_end_of_turn
        return False


class TranscriptCompleteEvent(Event, type=EventType.TRANSCRIPT_COMPLETE):  # type: ignore
    transcript: Transcript
