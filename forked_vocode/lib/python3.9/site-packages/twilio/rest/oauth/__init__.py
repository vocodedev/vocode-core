from warnings import warn

from twilio.rest.oauth.OauthBase import OauthBase
from twilio.rest.oauth.v1.device_code import DeviceCodeList
from twilio.rest.oauth.v1.oauth import OauthList
from twilio.rest.oauth.v1.openid_discovery import OpenidDiscoveryList
from twilio.rest.oauth.v1.token import TokenList
from twilio.rest.oauth.v1.user_info import UserInfoList


class Oauth(OauthBase):
    @property
    def oauth(self) -> OauthList:
        warn(
            "oauth is deprecated. Use v1.oauth instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.oauth

    @property
    def device_code(self) -> DeviceCodeList:
        warn(
            "device_code is deprecated. Use v1.device_code instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.device_code

    @property
    def openid_discovery(self) -> OpenidDiscoveryList:
        warn(
            "openid_discovery is deprecated. Use v1.openid_discovery instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.openid_discovery

    @property
    def token(self) -> TokenList:
        warn(
            "token is deprecated. Use v1.token instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.token

    @property
    def user_info(self) -> UserInfoList:
        warn(
            "user_info is deprecated. Use v1.user_info instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.user_info
