from warnings import warn

from twilio.rest.taskrouter.TaskrouterBase import TaskrouterBase
from twilio.rest.taskrouter.v1.workspace import WorkspaceList


class Taskrouter(TaskrouterBase):
    @property
    def workspaces(self) -> WorkspaceList:
        warn(
            "workspaces is deprecated. Use v1.workspaces instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.workspaces
