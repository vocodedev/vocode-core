from warnings import warn

from twilio.rest.chat.ChatBase import ChatBase
from twilio.rest.chat.v2.credential import CredentialList
from twilio.rest.chat.v2.service import ServiceList
from twilio.rest.chat.v3.channel import ChannelList


class Chat(ChatBase):
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

    @property
    def channels(self) -> ChannelList:
        warn(
            "channels is deprecated. Use v3.channels instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v3.channels
