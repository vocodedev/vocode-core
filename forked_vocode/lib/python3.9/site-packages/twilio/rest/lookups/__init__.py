from warnings import warn

from twilio.rest.lookups.LookupsBase import LookupsBase
from twilio.rest.lookups.v1.phone_number import PhoneNumberList


class Lookups(LookupsBase):
    @property
    def phone_numbers(self) -> PhoneNumberList:
        warn(
            "phone_numbers is deprecated. Use v1.phone_numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.phone_numbers
