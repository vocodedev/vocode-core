from warnings import warn

from twilio.rest.pricing.PricingBase import PricingBase
from twilio.rest.pricing.v1.messaging import MessagingList
from twilio.rest.pricing.v1.phone_number import PhoneNumberList
from twilio.rest.pricing.v2.country import CountryList
from twilio.rest.pricing.v2.number import NumberList
from twilio.rest.pricing.v2.voice import VoiceList


class Pricing(PricingBase):
    @property
    def messaging(self) -> MessagingList:
        warn(
            "messaging is deprecated. Use v1.messaging instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.messaging

    @property
    def phone_numbers(self) -> PhoneNumberList:
        warn(
            "phone_numbers is deprecated. Use v1.phone_numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.phone_numbers

    @property
    def voice(self) -> VoiceList:
        warn(
            "voice is deprecated. Use v2.voice instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.voice

    @property
    def countries(self) -> CountryList:
        warn(
            "countries is deprecated. Use v2.countries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.countries

    @property
    def numbers(self) -> NumberList:
        warn(
            "numbers is deprecated. Use v2.numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.numbers
