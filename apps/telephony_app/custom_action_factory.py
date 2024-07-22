from typing import Dict, Sequence, Type

from sms_send_appointment_noti import (
    SMSSendAppointmentNoti,
    SMSSendAppointmentNotiVocodeActionConfig,
)

from vocode.streaming.action.abstract_factory import AbstractActionFactory
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionConfig


class MyCustomActionFactory(AbstractActionFactory):
    def create_action(self, action_config: ActionConfig):
        print(action_config.type)
        if isinstance(action_config, SMSSendAppointmentNotiVocodeActionConfig):
            return SMSSendAppointmentNoti(action_config)
        else:
            raise Exception("Action type not supported by Agent config.")