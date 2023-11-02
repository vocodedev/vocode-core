from vocode.streaming.models.index_config import IndexConfig
from typing import Dict, Any
from vocode.streaming.models.index_config import IndexConfig
from vocode.streaming.vector_db.pinecone import PineconeDB
from vocode.streaming.utils.aws_s3 import load_from_s3
import logging
import base64 
import io 

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
        logger.debug(f"Preloaded {len(preloaded_vectors)} items from index")
        for doc in preloaded_vectors:
            object_id = doc.metadata.get("object_key")
            text_message = doc.page_content
            # logger.debug(f"Loading: {text_message} to vector_db_cache")
            try:
                audio_data = await load_from_s3(
                    bucket_name=bucket_name, 
                    object_key=object_id
                )
                audio_encoded: bytes = base64.b64encode(audio_data)
                vector_db_cache[text_message] = audio_encoded
                logger.debug(f"Loaded phrase: \"{text_message}\" to vector_db_cache")
            except Exception as e:
                logger.debug(f"Error loading object from S3: {str(e)}")
