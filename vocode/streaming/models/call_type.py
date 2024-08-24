from enum import Enum


class CallType(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    UNDEFINED = "undefined"
    CHAT = "chat"
