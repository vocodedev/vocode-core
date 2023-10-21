from warnings import warn

from twilio.rest.frontline_api.FrontlineApiBase import FrontlineApiBase
from twilio.rest.frontline_api.v1.user import UserList


class FrontlineApi(FrontlineApiBase):
    @property
    def users(self) -> UserList:
        warn(
            "users is deprecated. Use v1.users instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.users
