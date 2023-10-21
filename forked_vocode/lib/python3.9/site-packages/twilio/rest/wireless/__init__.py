from warnings import warn

from twilio.rest.wireless.WirelessBase import WirelessBase
from twilio.rest.wireless.v1.command import CommandList
from twilio.rest.wireless.v1.rate_plan import RatePlanList
from twilio.rest.wireless.v1.sim import SimList
from twilio.rest.wireless.v1.usage_record import UsageRecordList


class Wireless(WirelessBase):
    @property
    def usage_records(self) -> UsageRecordList:
        warn(
            "usage_records is deprecated. Use v1.usage_records instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.usage_records

    @property
    def commands(self) -> CommandList:
        warn(
            "commands is deprecated. Use v1.commands instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.commands

    @property
    def rate_plans(self) -> RatePlanList:
        warn(
            "rate_plans is deprecated. Use v1.rate_plans instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.rate_plans

    @property
    def sims(self) -> SimList:
        warn(
            "sims is deprecated. Use v1.sims instead.", DeprecationWarning, stacklevel=2
        )
        return self.v1.sims
