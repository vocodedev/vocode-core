from vocode.streaming.agent.openai_utils import merge_event_logs
from vocode.streaming.models.transcript import ActionStart, EventLog, Transcript


def format_anthropic_chat_messages_from_transcript(
    transcript: Transcript,
) -> list[dict]:
    # merge consecutive bot messages
    new_event_logs: list[EventLog] = merge_event_logs(event_logs=transcript.event_logs)

    # Removing BOT_ACTION_START so that it doesn't confuse the completion-y prompt, e.g.
    # BOT: BOT_ACTION_START: action_end_conversation
    # Right now, this version of context does not work for normal actions, only phrase trigger actions

    merged_event_logs_sans_bot_action_start = [
        event_log for event_log in new_event_logs if not isinstance(event_log, ActionStart)
    ]

    return [
        {
            "role": "user",
            "content": Transcript(event_logs=merged_event_logs_sans_bot_action_start).to_string(
                include_timestamps=False,
                mark_human_backchannels_with_brackets=True,
            ),
        },
        {"role": "assistant", "content": "BOT:"},
    ]
    # TODO: reliably count tokens of Anthropic messages so that we don't exceed the context window


def merge_bot_messages_for_langchain(messages: list[tuple]) -> list[tuple]:
    merged_messages: list[tuple] = []
    for role, message in messages:
        if role == "ai" and merged_messages and merged_messages[-1][0] == "ai":
            merged_messages[-1] = ("ai", merged_messages[-1][1] + message)
        else:
            merged_messages.append((role, message))
    return merged_messages
