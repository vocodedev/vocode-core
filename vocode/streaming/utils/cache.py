import os
from typing import Dict, List
from langchain.docstore.document import Document
from cachetools import LRUCache
from redis import Redis
from vocode.streaming.models.index_config import IndexConfig
from vocode.streaming.models.synthesizer import (
    SynthesizerConfig,
    ElevenLabsSynthesizerConfig
)
from vocode.streaming.vector_db.pinecone import PineconeDB
from vocode.streaming.utils.aws_s3 import load_from_s3_async
import logging

DAYS_TO_KEEP = 4
SECONDS_PER_DAY = 60 * 60 * 24

class RedisRenewableTTLCache:
    _redis_client = Redis(
        host=os.environ.get("REDISHOST", "localhost"),
        port=int(os.environ.get("REDISPORT", 6379)))
    _lru_cache = LRUCache(maxsize=2048)
    _ttl_in_seconds = int(os.environ.get("REDIS_TTL_IN_SECONDS", SECONDS_PER_DAY * DAYS_TO_KEEP))

    def get(self, key):
        if key in self._lru_cache:
            self._redis_client.expire(key, self._ttl_in_seconds)
            return self._lru_cache[key]

        value = self._redis_client.getex(key, ex=self._ttl_in_seconds)
        if not value is None:
            self._lru_cache[key] = value

        return value

    def set(self, key, value):
        self._lru_cache[key] = value

        # TODO: in the future we could use pickle.dumps/pickle.loads for classes, with caveats
        if self.value_type_is_supported(value):
            self._redis_client.setex(key, self._ttl_in_seconds, value)

    def value_type_is_supported(self, value) -> bool:
        return (
            isinstance(value, bytes)
            or isinstance(value, str)
            or isinstance(value, int)
            or isinstance(value, float)
        )
    
    def get_total_items(self) -> int:
        return len(self._lru_cache)
    
    def get_keys(self):
        # Get keys from the LRU cache
        lru_keys = list(self._lru_cache.keys())
        return lru_keys
    
    def is_empty(self) -> bool:
        return self.get_total_items() == 0

    
    async def load_from_index(
        self,
        synthesizer_config: SynthesizerConfig,
        load_size: int = 100,
        logger: logging.Logger = None
    ):
        import base64 
        import asyncio
        from botocore.client import Config
        config = Config(
            s3 = {
            'use_accelerate_endpoint': True
            }
        )
        from aiobotocore.session import get_session

        logger = logger or logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        
        index_config: IndexConfig = synthesizer_config.index_config
        vector_db = PineconeDB(index_config.pinecone_config)
        bucket_name = index_config.bucket_name
        
        filters = {}
        if isinstance(synthesizer_config, ElevenLabsSynthesizerConfig):
            filters = {
                "voice_id": synthesizer_config.voice_id,
                "stability": synthesizer_config.stability,
                "similarity_boost": synthesizer_config.similarity_boost,
            }


        # preloaded_vectors is a Dict [ voice_id : List of Documents]
        preloaded_vectors: Dict[str: List[Document]] = {}
        preloaded_vectors_count = 0
        vecs: List[Document] = await vector_db.retrieve_k_vectors_with_filter(
            filters=filters,
            k=load_size
        )
        preloaded_vectors_count += len(vecs)
        preloaded_vectors = vecs      
        await vector_db.tear_down()

        logger.debug(f"Preloading {preloaded_vectors_count} items from index")
    
        async def load_from_s3_and_save_task(
                cache: "RedisRenewableTTLCache", 
                doc: Document, 
                s3_client
            ):
            object_key= doc.metadata.get("object_key")
            text_message = doc.page_content
            cache_key = synthesizer_config.get_cache_key(text_message)
            audio_encoded = cache.get(cache_key)
            if audio_encoded is not None:
                return
            try:
                audio_data = await load_from_s3_async(bucket_name, object_key, s3_client)
                audio_encoded: bytes = base64.b64encode(audio_data)
                cache.set(cache_key, audio_encoded)
            except Exception as e:
                print(f"Error loading object from S3: {str(e)}")
                logger.debug(f"Error loading object from S3: {str(e)}")
            return

        try:
            aiosession = get_session()
            async with aiosession.create_client('s3', config=config) as _s3: 
                tasks = [
                    load_from_s3_and_save_task(self, doc, _s3)
                    for doc in preloaded_vectors
                ]
                await asyncio.gather(*tasks)
            logger.debug(f"Cache loaded! {self.get_total_items()} items.")
        except Exception as e:
            logger.debug(f"Error loading cache: {str(e)}")


if __name__ == "__main__":
    from vocode.streaming.models.vector_db import PineconeConfig
    import os
    from dotenv import load_dotenv
    import time
    import asyncio

    load_dotenv()
    pinecone_config = PineconeConfig(
        index=os.getenv("PINECONE_INDEX_NAME_URL"),
        api_key=os.getenv("PINECONE_API_KEY"),
        api_environment=os.getenv("PINECONE_ENVIRONMENT"),
        top_k=10
    )
    index_config = IndexConfig(
        pinecone_config=pinecone_config, 
        bucket_name="bluberry-synthesizer"
    )
    synthesizer_config = ElevenLabsSynthesizerConfig.from_telephone_output_device(
        voice_id="CzXriENDY3qWBMbH6JAj",
        stability=0.46,
        similarity_boost=0.75,
        model_id="eleven_turbo_v2",
        index_config=index_config,
        use_cache=False
    )
    redis_cache = RedisRenewableTTLCache()
    load_size = 100
    loop = asyncio.get_event_loop()
    start = time.time()
    loop.run_until_complete(
        redis_cache.load_from_index(
            synthesizer_config,
            load_size=load_size,
        )
    )
    print(redis_cache.get_keys())
    print(redis_cache.get_total_items())
    print(time.time() - start)