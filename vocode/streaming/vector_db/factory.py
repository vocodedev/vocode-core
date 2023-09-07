import logging
from typing import Optional
import aiohttp
from vocode.streaming.models.vector_db import PineconeConfig, VectorDBConfig
from vocode.streaming.vector_db.base_vector_db import VectorDB
from vocode.streaming.vector_db.pinecone import PineconeDB


class VectorDBFactory:
    def create_vector_db(
        self,
        vector_db_config: VectorDBConfig,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ) -> VectorDB:
        if isinstance(vector_db_config, PineconeConfig):
            return PineconeDB(vector_db_config, aiohttp_session=aiohttp_session)
        raise Exception("Invalid vector db config", vector_db_config.type)
