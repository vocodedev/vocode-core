from __future__ import annotations

from typing import Optional

from .base import API, api_base_url_v1


class Subscription(API):
    tier: str
    character_count: int
    character_limit: int
    can_extend_character_limit: bool
    allowed_to_extend_character_limit: bool
    next_character_count_reset_unix: int
    voice_limit: int
    professional_voice_limit: int
    can_extend_voice_limit: bool
    can_use_instant_voice_cloning: bool
    can_use_professional_voice_cloning: bool
    currency: Optional[str] = None
    status: str

    @classmethod
    def from_api(cls) -> Subscription:
        url = f"{api_base_url_v1}/user/subscription"
        response = API.get(url).json()
        return cls(**response)


class User(API):
    subscription: Subscription

    @classmethod
    def from_api(cls) -> User:
        url = f"{api_base_url_v1}/user"
        response = cls.get(url).json()
        return cls(**response)
