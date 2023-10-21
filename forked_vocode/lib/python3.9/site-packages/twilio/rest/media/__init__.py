from warnings import warn

from twilio.rest.media.MediaBase import MediaBase
from twilio.rest.media.v1.media_processor import MediaProcessorList
from twilio.rest.media.v1.media_recording import MediaRecordingList
from twilio.rest.media.v1.player_streamer import PlayerStreamerList


class Media(MediaBase):
    @property
    def media_processor(self) -> MediaProcessorList:
        warn(
            "media_processor is deprecated. Use v1.media_processor instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.media_processor

    @property
    def media_recording(self) -> MediaRecordingList:
        warn(
            "media_recording is deprecated. Use v1.media_recording instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.media_recording

    @property
    def player_streamer(self) -> PlayerStreamerList:
        warn(
            "player_streamer is deprecated. Use v1.player_streamer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.player_streamer
