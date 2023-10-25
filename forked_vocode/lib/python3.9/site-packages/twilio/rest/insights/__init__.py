from warnings import warn

from twilio.rest.insights.InsightsBase import InsightsBase
from twilio.rest.insights.v1.call import CallList
from twilio.rest.insights.v1.call_summaries import CallSummariesList
from twilio.rest.insights.v1.conference import ConferenceList
from twilio.rest.insights.v1.room import RoomList
from twilio.rest.insights.v1.setting import SettingList


class Insights(InsightsBase):
    @property
    def settings(self) -> SettingList:
        warn(
            "settings is deprecated. Use v1.settings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.settings

    @property
    def calls(self) -> CallList:
        warn(
            "calls is deprecated. Use v1.calls instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.calls

    @property
    def call_summaries(self) -> CallSummariesList:
        warn(
            "call_summaries is deprecated. Use v1.call_summaries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.call_summaries

    @property
    def conferences(self) -> ConferenceList:
        warn(
            "conferences is deprecated. Use v1.conferences instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.conferences

    @property
    def rooms(self) -> RoomList:
        warn(
            "rooms is deprecated. Use v1.rooms instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.rooms
