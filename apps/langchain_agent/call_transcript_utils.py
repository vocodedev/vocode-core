import os
from typing import Optional

CALL_TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "call_transcripts")


def add_transcript(conversation_id: str, transcript: dict) -> None:
    transcript_path = os.path.join(
        CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id)
    )
    with open(transcript_path, "a") as f:
        for message in transcript["messages"]:
            f.write("{}: {}\n".format(message["sender"], message["text"]))


def get_transcript(conversation_id: str) -> Optional[str]:
    transcript_path = os.path.join(
        CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id)
    )
    if os.path.exists(transcript_path):
        with open(transcript_path, "r") as f:
            return f.read()


def delete_transcript(conversation_id: str) -> bool:
    transcript_path = os.path.join(
        CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id)
    )
    if os.path.exists(transcript_path):
        os.remove(transcript_path)
        return True
    return False
