from warnings import warn

from twilio.rest.notify.NotifyBase import NotifyBase
from twilio.rest.notify.v1.credential import CredentialList
from twilio.rest.notify.v1.service import ServiceList


class Notify(NotifyBase):
    @property
    def credentials(self) -> CredentialList:
        warn(
            "credentials is deprecated. Use v1.credentials instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.credentials

    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v1.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.services
