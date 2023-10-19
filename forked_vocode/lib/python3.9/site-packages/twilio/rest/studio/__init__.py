from warnings import warn

from twilio.rest.studio.StudioBase import StudioBase
from twilio.rest.studio.v2.flow import FlowList
from twilio.rest.studio.v2.flow_validate import FlowValidateList


class Studio(StudioBase):
    @property
    def flows(self) -> FlowList:
        warn(
            "flows is deprecated. Use v2.flows instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.flows

    @property
    def flow_validate(self) -> FlowValidateList:
        warn(
            "flow_validate is deprecated. Use v2.flow_validate instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.flow_validate
