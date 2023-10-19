from warnings import warn

from twilio.rest.sync.SyncBase import SyncBase
from twilio.rest.sync.v1.service import ServiceList


class Sync(SyncBase):
    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v1.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.services
