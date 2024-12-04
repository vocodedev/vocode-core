from abc import ABC, abstractmethod

from vocode_velocity.streaming.action.base_action import BaseAction
from vocode_velocity.streaming.models.actions import ActionConfig


class AbstractActionFactory(ABC):
    @abstractmethod
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        pass
