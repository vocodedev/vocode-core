class VectorDB:
    async def add_texts(self):
        raise NotImplementedError

    async def similarity_search_with_score(self):
        raise NotImplementedError
