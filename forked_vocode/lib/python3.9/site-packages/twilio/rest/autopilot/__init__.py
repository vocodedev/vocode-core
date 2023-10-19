from warnings import warn

from twilio.rest.autopilot.AutopilotBase import AutopilotBase
from twilio.rest.autopilot.v1.assistant import AssistantList
from twilio.rest.autopilot.v1.restore_assistant import RestoreAssistantList


class Autopilot(AutopilotBase):
    @property
    def assistants(self) -> AssistantList:
        warn(
            "assistants is deprecated. Use v1.assistants instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.assistants

    @property
    def restore_assistant(self) -> RestoreAssistantList:
        warn(
            "restore_assistant is deprecated. Use v1.restore_assistant instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.restore_assistant
