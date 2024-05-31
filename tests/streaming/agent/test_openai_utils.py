from vocode.streaming.agent.openai_utils import format_openai_chat_messages_from_transcript
from vocode.streaming.models.actions import (
    ACTION_FINISHED_FORMAT_STRING,
    ActionConfig,
    ActionInput,
    ActionOutput,
    PhraseBasedActionTrigger,
    PhraseBasedActionTriggerConfig,
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import ActionFinish, ActionStart, Message, Transcript


class WeatherActionConfig(ActionConfig, type="weather"):
    pass


def create_fake_vocode_phrase_trigger():
    return PhraseBasedActionTrigger(config=PhraseBasedActionTriggerConfig(phrase_triggers=[]))


def test_format_openai_chat_messages_from_transcript():
    test_action_input_nophrase = ActionInput(
        action_config=WeatherActionConfig(),
        conversation_id="asdf",
        params={},
    )
    test_action_input_phrase = ActionInput(
        action_config=WeatherActionConfig(action_trigger=create_fake_vocode_phrase_trigger()),
        conversation_id="asdf",
        params={},
    )

    test_cases = [
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(
                            sender=Sender.BOT,
                            text="How are you doing today?",
                            is_final=True,
                        ),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {"role": "assistant", "content": "Hello! How are you doing today?"},
                {"role": "user", "content": "I'm doing well, thanks!"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(sender=Sender.BOT, text="How are", is_final=False),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {"role": "assistant", "content": "Hello! How are-"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(sender=Sender.HUMAN, text="Hello, what's the weather like?"),
                        ActionStart(
                            action_type="weather",
                            action_input=test_action_input_nophrase,
                        ),
                        ActionFinish(
                            action_type="weather",
                            action_input=test_action_input_nophrase,
                            action_output=ActionOutput(action_type="weather", response={}),
                        ),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "some prompt",
            ),
            [
                {"role": "system", "content": "some prompt"},
                {"role": "assistant", "content": "Hello!"},
                {
                    "role": "user",
                    "content": "Hello, what's the weather like?",
                },
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {"name": "weather", "arguments": "{}"},
                },
                {
                    "role": "function",
                    "name": "weather",
                    "content": ACTION_FINISHED_FORMAT_STRING.format(
                        action_name="weather", action_output="{}"
                    ),
                },
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(sender=Sender.HUMAN, text="Hello, what's the weather like?"),
                        ActionStart(
                            action_type="weather",
                            action_input=test_action_input_phrase,
                        ),
                        ActionFinish(
                            action_type="weather",
                            action_input=test_action_input_phrase,
                            action_output=ActionOutput(action_type="weather", response={}),
                        ),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "some prompt",
            ),
            [
                {"role": "system", "content": "some prompt"},
                {"role": "assistant", "content": "Hello!"},
                {
                    "role": "user",
                    "content": "Hello, what's the weather like?",
                },
                {
                    "role": "function",
                    "name": "weather",
                    "content": ACTION_FINISHED_FORMAT_STRING.format(
                        action_name="weather", action_output="{}"
                    ),
                },
            ],
        ),
    ]

    for params, expected_output in test_cases:
        assert format_openai_chat_messages_from_transcript(*params) == expected_output


def test_format_openai_chat_messages_from_transcript_context_limit():
    test_cases = [
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(
                            sender=Sender.BOT,
                            text="How are you doing today? I'm doing amazing thank you so much for asking!",
                        ),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "aaaa " * 1862,
            ),
            [
                {"role": "system", "content": "aaaa " * 1862},
                {"role": "user", "content": "I'm doing well, thanks!"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(
                            sender=Sender.BOT,
                            text="How are you doing today? I'm doing amazing thank you so much for asking!",
                            is_final=True,
                        ),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                        Message(sender=Sender.BOT, text="aaaa " * 1862),
                        Message(sender=Sender.HUMAN, text="What? What did you just say???"),
                        Message(
                            sender=Sender.BOT,
                            text="My apologies, there was an error. Please ignore my previous message",
                            is_final=True,
                        ),
                        Message(
                            sender=Sender.HUMAN,
                            text="Don't worry I ignored all 1862 * 5 characters of it.",
                        ),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {
                    "content": "What? What did you just say???",
                    "role": "user",
                },
                {
                    "role": "assistant",
                    "content": "My apologies, there was an error. Please ignore my previous message",
                },
                {
                    "role": "user",
                    "content": "Don't worry I ignored all 1862 * 5 characters of it.",
                },
            ],
        ),
    ]

    for params, expected_output in test_cases:
        assert format_openai_chat_messages_from_transcript(*params) == expected_output


def test_format_openai_chat_messages_from_transcript_context_limit():
    test_cases = [
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!", is_final=True),
                        Message(
                            sender=Sender.BOT,
                            text="How are you doing today? I'm doing amazing thank you so much for asking!",
                        ),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "aaaa " * 1862,
            ),
            [
                {"role": "system", "content": "aaaa " * 1862},
                {"role": "user", "content": "I'm doing well, thanks!"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(
                            sender=Sender.BOT,
                            text="How are you doing today? I'm doing amazing thank you so much for asking!",
                            is_final=True,
                        ),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                        Message(sender=Sender.BOT, text="aaaa " * 1862),
                        Message(sender=Sender.HUMAN, text="What? What did you just say???"),
                        Message(
                            sender=Sender.BOT,
                            text="My apologies, there was an error. Please ignore my previous message",
                            is_final=True,
                        ),
                        Message(
                            sender=Sender.HUMAN,
                            text="Don't worry I ignored all 1862 * 5 characters of it.",
                        ),
                    ]
                ),
                "gpt-3.5-turbo-0613",
                None,
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {
                    "content": "What? What did you just say???",
                    "role": "user",
                },
                {
                    "role": "assistant",
                    "content": "My apologies, there was an error. Please ignore my previous message",
                },
                {
                    "role": "user",
                    "content": "Don't worry I ignored all 1862 * 5 characters of it.",
                },
            ],
        ),
    ]

    for params, expected_output in test_cases:
        assert format_openai_chat_messages_from_transcript(*params) == expected_output
