from warnings import warn

from twilio.rest.microvisor.MicrovisorBase import MicrovisorBase
from twilio.rest.microvisor.v1.account_config import AccountConfigList
from twilio.rest.microvisor.v1.account_secret import AccountSecretList
from twilio.rest.microvisor.v1.app import AppList
from twilio.rest.microvisor.v1.device import DeviceList


class Microvisor(MicrovisorBase):
    @property
    def account_configs(self) -> AccountConfigList:
        warn(
            "account_configs is deprecated. Use v1.account_configs instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.account_configs

    @property
    def account_secrets(self) -> AccountSecretList:
        warn(
            "account_secrets is deprecated. Use v1.account_secrets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.account_secrets

    @property
    def apps(self) -> AppList:
        warn(
            "apps is deprecated. Use v1.apps instead.", DeprecationWarning, stacklevel=2
        )
        return self.v1.apps

    @property
    def devices(self) -> DeviceList:
        warn(
            "devices is deprecated. Use v1.devices instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.devices
