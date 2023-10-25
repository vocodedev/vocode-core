from warnings import warn

from twilio.rest.ip_messaging.IpMessagingBase import IpMessagingBase
from twilio.rest.ip_messaging.v2.credential import CredentialList
from twilio.rest.ip_messaging.v2.service import ServiceList


class IpMessaging(IpMessagingBase):
    @property
    def credentials(self) -> CredentialList:
        warn(
            "credentials is deprecated. Use v2.credentials instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.credentials

    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v2.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.services
