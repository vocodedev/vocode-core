from warnings import warn

from twilio.rest.numbers.NumbersBase import NumbersBase
from twilio.rest.numbers.v2.regulatory_compliance import RegulatoryComplianceList


class Numbers(NumbersBase):
    @property
    def regulatory_compliance(self) -> RegulatoryComplianceList:
        warn(
            "regulatory_compliance is deprecated. Use v2.regulatory_compliance instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.regulatory_compliance
