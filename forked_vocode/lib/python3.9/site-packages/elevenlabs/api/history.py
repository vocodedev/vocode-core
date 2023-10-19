from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import root_validator

from .base import API, Listable, api_base_url_v1
from .voice import VoiceSettings


class FeedbackItem(API):
    thumbs_up: bool
    feedback: str
    emotions: bool
    inaccurate_clone: bool
    glitches: bool
    audio_quality: bool
    other: bool
    review_status: str


class HistoryItem(API):
    history_item_id: str
    request_id: Optional[str] = None
    voice_id: str
    text: str
    date: Optional[datetime] = None
    date_unix: int
    character_count_change_from: int
    character_count_change_to: int
    character_count_change: Optional[int] = None
    content_type: str
    settings: Optional[VoiceSettings] = None
    feedback: Optional[FeedbackItem] = None
    _audio: Optional[bytes] = None

    @root_validator(skip_on_failure=True)
    def computed(cls, values):
        # Compute character count field
        change_from = values["character_count_change_from"]
        change_to = values["character_count_change_to"]
        values["character_count_change"] = change_to - change_from
        # Compute datetime field
        values["date"] = datetime.utcfromtimestamp(values["date_unix"])
        return values

    @classmethod
    def from_id(cls, history_item_id: str) -> HistoryItem:
        url = f"{api_base_url_v1}/history/{history_item_id}"
        response = API.get(url).json()
        return cls(**response)

    @property
    def audio(self) -> bytes:
        url = f"{api_base_url_v1}/history/{self.history_item_id}/audio"
        if self._audio is None:
            self._audio = API.get(url).content
        return self._audio

    def delete(self):
        API.delete(f"{api_base_url_v1}/history/{self.history_item_id}")


class History(Listable, API):
    last_history_item_id: Optional[str] = None
    history: List[HistoryItem]
    has_more: bool

    @classmethod
    def from_api(
        cls, page_size: int = 100, start_after_history_item_id: Optional[str] = None
    ) -> History:
        assert page_size < 1000, (
            "page_size must be less than 1000, change start_after_history_item_id"
            " instead."
        )
        data = dict(
            page_size=page_size,
            start_after_history_item_id=start_after_history_item_id,
        )
        url = f"{api_base_url_v1}/history"
        response = API.get(url, params=data).json()
        return cls(**response)

    @property
    def items(self):
        return self.history

    def __iter__(self):
        """Lazy iterator over history items"""
        for item in self.history:
            yield item
        while self.has_more:
            history_next = self.from_api(
                start_after_history_item_id=self.last_history_item_id
            )
            self.history.extend(history_next.history)
            self.has_more = history_next.has_more
            self.last_history_item_id = history_next.last_history_item_id

            for item in self.history:
                yield item
