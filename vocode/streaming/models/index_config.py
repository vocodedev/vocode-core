from vocode.streaming.models.vector_db import PineconeConfig

from .model import BaseModel

class IndexConfig(BaseModel):
    pinecone_config: PineconeConfig
    bucket_name: str