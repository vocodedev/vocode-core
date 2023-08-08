from enum import Enum


class CallStatus(Enum):
    AUTOCALLING = "autocalling"
    TRANSFERRING = "transferring"
    TRANSFERRED = "transferred"
    ENDED_BEFORE_TRANSFER = "ended before transfer"
    ENDED_AFTER_TRANSFER = "ended after transfer"
    PENDING = None  # default