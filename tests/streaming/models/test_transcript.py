import asyncio
from vocode.streaming.models.actions import (
    ActionInput,
    ActionOutput,
    TwilioPhoneCallActionInput,
)
from vocode.streaming.models.transcript import ActionStart, ActionFinish
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Message
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.action.nylas_send_email import (
    NylasSendEmailActionConfig,
    NylasSendEmailParameters,
    NylasSendEmailResponse,
)


def test_transcript_to_string():
    transcript = Transcript(
        event_logs=[
            Message(sender=Sender.BOT, text="What up"),
            Message(
                sender=Sender.HUMAN,
                text="Send me an email you bot. My email is du@de.com",
            ),
            ActionStart(
                action_type="action_nylas_send_email",
                action_input=TwilioPhoneCallActionInput(
                    action_config=NylasSendEmailActionConfig(),
                    conversation_id="123",
                    params=NylasSendEmailParameters(
                        recipient_email="du@de.com",
                        body="What up",
                        subject="This is the bot",
                    ),
                    _user_message_tracker=asyncio.Event(),
                    twilio_sid="123",
                ),
            ),
            ActionFinish(
                action_type="action_nylas_send_email",
                action_output=ActionOutput(
                    action_type="action_nylas_send_email",
                    response=NylasSendEmailResponse(success=True),
                ),
            ),
        ]
    )

    assert (
        transcript.to_string()
        == """BOT: What up
HUMAN: Send me an email you bot. My email is du@de.com
ACTION_WORKER: params={'recipient_email': 'du@de.com', 'body': 'What up', 'subject': 'This is the bot'}
ACTION_WORKER: action_type='action_nylas_send_email' response={'success': True}"""
    )


def test_transcript_to_string_no_phone_input():
    transcript = Transcript(
        event_logs=[
            Message(sender=Sender.BOT, text="What up"),
            Message(
                sender=Sender.HUMAN,
                text="Send me an email you bot. My email is du@de.com",
            ),
            ActionStart(
                action_type="action_nylas_send_email",
                action_input=ActionInput(
                    action_config=NylasSendEmailActionConfig(),
                    conversation_id="123",
                    params=NylasSendEmailParameters(
                        recipient_email="du@de.com",
                        body="What up",
                        subject="This is the bot",
                    ),
                    _user_message_tracker=asyncio.Event(),
                ),
            ),
            ActionFinish(
                action_type="action_nylas_send_email",
                action_output=ActionOutput(
                    action_type="action_nylas_send_email",
                    response=NylasSendEmailResponse(success=True),
                ),
            ),
        ]
    )

    assert (
        transcript.to_string()
        == """BOT: What up
HUMAN: Send me an email you bot. My email is du@de.com
ACTION_WORKER: params={'recipient_email': 'du@de.com', 'body': 'What up', 'subject': 'This is the bot'}
ACTION_WORKER: action_type='action_nylas_send_email' response={'success': True}"""
    )
