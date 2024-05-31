from typing import Optional

from loguru import logger

from vocode.streaming.utils.redis import initialize_redis_bytes
from vocode.streaming.utils.singleton import Singleton


class AudioCache(Singleton):
    def __init__(self):
        self.redis = initialize_redis_bytes()
        self.disabled = False

    @staticmethod
    async def safe_create():
        if AudioCache in Singleton._instances:
            return Singleton._instances[AudioCache]

        audio_cache = AudioCache()
        try:
            await audio_cache.redis.ping()
        except Exception:
            logger.warning("Redis ping failed on startup, disabling audio cache")
            audio_cache.disabled = True
        return audio_cache

    def get_audio_key(self, voice_identifier: str, text: str) -> str:
        return f"audio_cache:{voice_identifier}:{text}"

    async def get_audio(self, voice_identifier: str, text: str) -> Optional[bytes]:
        audio_key = self.get_audio_key(voice_identifier, text)
        if self.disabled:
            return None
        return await self.redis.get(audio_key)

    async def set_audio(
        self, voice_identifier: str, text: str, audio: bytes, ttl: Optional[int] = None
    ):
        # TODO: cache eviction
        if self.disabled:
            logger.warning("Audio cache is disabled")
            return
        logger.info(f"Setting audio for {voice_identifier} {text}")
        audio_key = self.get_audio_key(voice_identifier, text)
        await self.redis.set(audio_key, audio)
        if ttl is not None:
            await self.redis.expire(audio_key, ttl)
