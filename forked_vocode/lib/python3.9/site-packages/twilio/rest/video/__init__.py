from warnings import warn

from twilio.rest.video.VideoBase import VideoBase
from twilio.rest.video.v1.composition import CompositionList
from twilio.rest.video.v1.composition_hook import CompositionHookList
from twilio.rest.video.v1.composition_settings import CompositionSettingsList
from twilio.rest.video.v1.recording import RecordingList
from twilio.rest.video.v1.recording_settings import RecordingSettingsList
from twilio.rest.video.v1.room import RoomList


class Video(VideoBase):
    @property
    def compositions(self) -> CompositionList:
        warn(
            "compositions is deprecated. Use v1.compositions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.compositions

    @property
    def composition_hooks(self) -> CompositionHookList:
        warn(
            "composition_hooks is deprecated. Use v1.composition_hooks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.composition_hooks

    @property
    def composition_settings(self) -> CompositionSettingsList:
        warn(
            "composition_settings is deprecated. Use v1.composition_settings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.composition_settings

    @property
    def recordings(self) -> RecordingList:
        warn(
            "recordings is deprecated. Use v1.recordings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.recordings

    @property
    def recording_settings(self) -> RecordingSettingsList:
        warn(
            "recording_settings is deprecated. Use v1.recording_settings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.recording_settings

    @property
    def rooms(self) -> RoomList:
        warn(
            "rooms is deprecated. Use v1.rooms instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.rooms
