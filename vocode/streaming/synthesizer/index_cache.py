from vocode.streaming.models.index_config import IndexConfig
from typing import Dict, Any
from vocode.streaming.models.index_config import IndexConfig
from vocode.streaming.vector_db.pinecone import PineconeDB
from vocode.streaming.utils.aws_s3 import load_from_s3_async
import logging
import base64 
import asyncio
from aiobotocore.session import get_session
from botocore.client import Config
config = Config(
    s3 = {
    'use_accelerate_endpoint': True
    }
)

async def load_index_cache(
          index_config: IndexConfig, 
          vector_db_cache: Dict[str, Any],
          voice_filters: Dict[str, Any] = None,
          cache_size: int = 100,
          logger: logging.Logger = None
    ):
    logger = logger or logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    vector_db = PineconeDB(index_config.pinecone_config)
    bucket_name = index_config.bucket_name
    
    preloaded_vectors = await vector_db.retrieve_k_vectors_with_filter(
            filters=voice_filters,
            k=cache_size
    )
    await vector_db.tear_down()
    print(f"{len(preloaded_vectors)} preloaded vectors")
    logger.debug(f"Preloaded {len(preloaded_vectors)} items from index")
   
    async def load_from_s3_and_save_task(vector_db_cache, doc, s3_client):
        object_key= doc.metadata.get("object_key")
        text_message = doc.page_content
        if text_message in vector_db_cache:
            logger.debug(f"Phrase: \"{text_message}\" already exists in vector_db_cache")
            return
        try:
            audio_data = await load_from_s3_async(bucket_name, object_key, s3_client)
            audio_encoded: bytes = base64.b64encode(audio_data)
            vector_db_cache[text_message] = audio_encoded
            # logger.debug(f"Loaded phrase: \"{text_message}\" to vector_db_cache")
        except Exception as e:
            print(f"Error loading object from S3: {str(e)}")
            logger.debug(f"Error loading object from S3: {str(e)}")
        return

    try:
        aiosession = get_session()
        logger.debug(f"Loading cache")
        async with aiosession.create_client('s3', config=config) as _s3: 
            tasks = [load_from_s3_and_save_task(vector_db_cache, doc, _s3)
                    for doc in preloaded_vectors]
            await asyncio.gather(*tasks)
        logger.debug(f"Cache loaded! {len(vector_db_cache)} items.")
    except Exception as e:
        logger.debug(f"Error loading cache: {str(e)}")

if __name__ == "__main__":
    from vocode.streaming.models.vector_db import PineconeConfig
    import os
    from dotenv import load_dotenv
    import time

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
    cache_size = 1000
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