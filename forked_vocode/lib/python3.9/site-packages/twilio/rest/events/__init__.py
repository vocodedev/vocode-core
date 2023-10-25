from warnings import warn

from twilio.rest.events.EventsBase import EventsBase
from twilio.rest.events.v1.event_type import EventTypeList
from twilio.rest.events.v1.schema import SchemaList
from twilio.rest.events.v1.sink import SinkList
from twilio.rest.events.v1.subscription import SubscriptionList


class Events(EventsBase):
    @property
    def event_types(self) -> EventTypeList:
        warn(
            "event_types is deprecated. Use v1.event_types instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.event_types

    @property
    def schemas(self) -> SchemaList:
        warn(
            "schemas is deprecated. Use v1.schemas instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.schemas

    @property
    def sinks(self) -> SinkList:
        warn(
            "sinks is deprecated. Use v1.sinks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.sinks

    @property
    def subscriptions(self) -> SubscriptionList:
        warn(
            "subscriptions is deprecated. Use v1.subscriptions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.subscriptions
