from warnings import warn

from twilio.rest.trunking.TrunkingBase import TrunkingBase
from twilio.rest.trunking.v1.trunk import TrunkList


class Trunking(TrunkingBase):
    @property
    def trunks(self) -> TrunkList:
        warn(
            "trunks is deprecated. Use v1.trunks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.trunks
