from warnings import warn

from twilio.rest.monitor.MonitorBase import MonitorBase
from twilio.rest.monitor.v1.alert import AlertList
from twilio.rest.monitor.v1.event import EventList


class Monitor(MonitorBase):
    @property
    def alerts(self) -> AlertList:
        warn(
            "alerts is deprecated. Use v1.alerts instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.alerts

    @property
    def events(self) -> EventList:
        warn(
            "events is deprecated. Use v1.events instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.events
