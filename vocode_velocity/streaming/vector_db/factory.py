from typing import TYPE_CHECKING, Optional

import aiohttp

from vocode.streaming.models.vector_db import PineconeConfig, VectorDBConfig
from vocode.streaming.vector_db.base_vector_db import VectorDB

if TYPE_CHECKING:
    from vocode.streaming.vector_db.pinecone import PineconeDB


class VectorDBFactory:
    def create_vector_db(
        self,
        vector_db_config: VectorDBConfig,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ) -> VectorDB:
        if isinstance(vector_db_config, PineconeConfig):
            return self._get_pinecone_db(vector_db_config, aiohttp_session)
        raise Exception("Invalid vector db config", vector_db_config.type)

    def _get_pinecone_db(
        self, vector_db_config: PineconeConfig, aiohttp_session: Optional[aiohttp.ClientSession]
    ) -> "PineconeDB":
        try:
            from vocode.streaming.vector_db.pinecone import PineconeDB

            return PineconeDB(vector_db_config, aiohttp_session=aiohttp_session)
        except ImportError as e:
            raise ImportError(
                f"Missing required dependancies for VectorDB {vector_db_config.type}"
            ) from e
