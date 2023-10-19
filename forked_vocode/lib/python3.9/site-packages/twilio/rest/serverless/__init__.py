from warnings import warn

from twilio.rest.serverless.ServerlessBase import ServerlessBase
from twilio.rest.serverless.v1.service import ServiceList


class Serverless(ServerlessBase):
    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v1.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.services
