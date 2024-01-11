from vocode.streaming.models.vector_db import VectorDBConfig
from .model import BaseModel

class IndexConfig(BaseModel):
    vector_db_config: VectorDBConfig
    bucket_name: str