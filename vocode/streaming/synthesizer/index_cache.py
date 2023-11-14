from vocode.streaming.models.index_config import IndexConfig
from typing import Dict, Any, List
from langchain.docstore.document import Document
from vocode.streaming.models.index_config import IndexConfig
from vocode.streaming.vector_db.pinecone import PineconeDB
from vocode.streaming.utils.aws_s3 import load_from_s3_async
import logging

from typing import Any, Dict
from pydantic import BaseModel

class VoiceCacheItem(BaseModel):
    data: Dict[str, Any]

class VoiceCacheModel:
    caches: Dict[str, VoiceCacheItem] = {}

    @classmethod
    def add_cache(cls, voice_id: str, data: Dict[str, Any] = {}):
        """Add an item to the cache."""
        cache_item = VoiceCacheItem(data=data)
        cls.caches[voice_id] = cache_item

    @classmethod
    def get_cache(cls, voice_id: str) -> VoiceCacheItem:
        """Get an item from the cache."""
        return cls.caches.get(voice_id)

    @classmethod
    def remove_cache(cls, voice_id: str):
        """Remove an item from the cache."""
        if voice_id in cls.caches:
            del cls.caches[voice_id]

    @classmethod
    def extend_cache_entry(cls, voice_id: str, data: Dict[str, Any]):
        """Extend the data of an entry in the cache."""
        if voice_id in cls.caches:
            cls.caches[voice_id].data.update(data)

    def __str__(self):
        """String representation of the cache state."""
        return f"VoiceCacheModel(caches={self.caches})"

    def __len__(self):
        """Return the total number of items across all caches."""
        return sum(len(cache_item.data) for cache_item in self.caches.values())
    
    def is_empty(self):
        """Check if the cache is empty."""
        return len(self) == 0

class VoiceSettingsObject(BaseModel):
    id: str
    filters: dict

async def load_index_cache(
          index_config: IndexConfig, 
          vector_db_cache: VoiceCacheModel,
          voices: [VoiceSettingsObject] = None,
          cache_size: int = 100,
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
    
    vector_db = PineconeDB(index_config.pinecone_config)
    bucket_name = index_config.bucket_name
    
    # preloaded_vectors is a Dict [ voice_id : List of Documents]
    preloaded_vectors: Dict[str: List[Document]] = {}
    preloaded_vectors_count = 0
    for i in range(len(voices)):
        selected_voice: VoiceSettingsObject = voices[i]
        # create a subcache for voice with id 
        vector_db_cache.add_cache(voice_id=selected_voice.id)
        vecs: List[Document] = await vector_db.retrieve_k_vectors_with_filter(
            filters=selected_voice.filters,
            k=cache_size
        )
        preloaded_vectors_count += len(vecs)
        preloaded_vectors[selected_voice.id] = vecs
    
    await vector_db.tear_down()
    print(f"Preloading {preloaded_vectors_count} items from index")
    logger.debug(f"Preloading {preloaded_vectors_count} items from index")
   
    async def load_from_s3_and_save_task(
            vector_db_cache: VoiceCacheModel, 
            voice_id: str,
            doc, 
            s3_client
        ):
        object_key= doc.metadata.get("object_key")
        text_message = doc.page_content
        if text_message in vector_db_cache.get_cache(voice_id).data:
            logger.debug(f"Phrase: \"{text_message}\" already exists in vector DB cache")
            return
        try:
            audio_data = await load_from_s3_async(bucket_name, object_key, s3_client)
            audio_encoded: bytes = base64.b64encode(audio_data)
            vector_db_cache.extend_cache_entry(
                voice_id=voice_id, 
                data={text_message : audio_encoded}
            )
            # vector_db_cache[text_message] = audio_encoded
            # logger.debug(f"Loaded phrase: \"{text_message}\" to vector_db_cache")
        except Exception as e:
            print(f"Error loading object from S3: {str(e)}")
            logger.debug(f"Error loading object from S3: {str(e)}")
        return

    try:
        aiosession = get_session()
        logger.debug(f"Loading cache")
        for i, voice_id in enumerate(preloaded_vectors.keys()):        
            async with aiosession.create_client('s3', config=config) as _s3: 
                tasks = [load_from_s3_and_save_task(vector_db_cache, voice_id, doc, _s3)
                        for doc in preloaded_vectors[voice_id]]
                await asyncio.gather(*tasks)
        logger.debug(f"Cache loaded! {len(vector_db_cache)} items.")
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
    vector_db_cache = {}
    cache_size = 2000
    loop = asyncio.get_event_loop()
    start = time.time()
    loop.run_until_complete(
        load_index_cache(
            index_config,
            vector_db_cache,
            cache_size=cache_size
        )
    )
    print(vector_db_cache.keys())
    print(len(vector_db_cache))
    print(time.time() - start)