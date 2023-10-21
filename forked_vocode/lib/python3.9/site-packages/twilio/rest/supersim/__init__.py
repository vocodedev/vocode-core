from warnings import warn

from twilio.rest.supersim.SupersimBase import SupersimBase
from twilio.rest.supersim.v1.esim_profile import EsimProfileList
from twilio.rest.supersim.v1.fleet import FleetList
from twilio.rest.supersim.v1.ip_command import IpCommandList
from twilio.rest.supersim.v1.network import NetworkList
from twilio.rest.supersim.v1.network_access_profile import NetworkAccessProfileList
from twilio.rest.supersim.v1.settings_update import SettingsUpdateList
from twilio.rest.supersim.v1.sim import SimList
from twilio.rest.supersim.v1.sms_command import SmsCommandList
from twilio.rest.supersim.v1.usage_record import UsageRecordList


class Supersim(SupersimBase):
    @property
    def esim_profiles(self) -> EsimProfileList:
        warn(
            "esim_profiles is deprecated. Use v1.esim_profiles instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.esim_profiles

    @property
    def fleets(self) -> FleetList:
        warn(
            "fleets is deprecated. Use v1.fleets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.fleets

    @property
    def ip_commands(self) -> IpCommandList:
        warn(
            "ip_commands is deprecated. Use v1.ip_commands instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.ip_commands

    @property
    def networks(self) -> NetworkList:
        warn(
            "networks is deprecated. Use v1.networks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.networks

    @property
    def network_access_profiles(self) -> NetworkAccessProfileList:
        warn(
            "network_access_profiles is deprecated. Use v1.network_access_profiles instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.network_access_profiles

    @property
    def settings_updates(self) -> SettingsUpdateList:
        warn(
            "settings_updates is deprecated. Use v1.settings_updates instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.settings_updates

    @property
    def sims(self) -> SimList:
        warn(
            "sims is deprecated. Use v1.sims instead.", DeprecationWarning, stacklevel=2
        )
        return self.v1.sims

    @property
    def sms_commands(self) -> SmsCommandList:
        warn(
            "sms_commands is deprecated. Use v1.sms_commands instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.sms_commands

    @property
    def usage_records(self) -> UsageRecordList:
        warn(
            "usage_records is deprecated. Use v1.usage_records instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.usage_records
