from warnings import warn

from twilio.rest.routes.RoutesBase import RoutesBase
from twilio.rest.routes.v2.phone_number import PhoneNumberList
from twilio.rest.routes.v2.sip_domain import SipDomainList
from twilio.rest.routes.v2.trunk import TrunkList


class Routes(RoutesBase):
    @property
    def phone_numbers(self) -> PhoneNumberList:
        warn(
            "phone_numbers is deprecated. Use v2.phone_numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.phone_numbers

    @property
    def sip_domains(self) -> SipDomainList:
        warn(
            "sip_domains is deprecated. Use v2.sip_domains instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.sip_domains

    @property
    def trunks(self) -> TrunkList:
        warn(
            "trunks is deprecated. Use v2.trunks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.trunks
