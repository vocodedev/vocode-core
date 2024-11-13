from enum import Enum


class CallType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    UNDEFINED = "undefined"
    CHAT = "chat"
