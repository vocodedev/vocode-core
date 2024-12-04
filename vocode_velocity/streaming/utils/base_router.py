from fastapi import APIRouter


class BaseRouter:
    def get_router(self) -> APIRouter:
        raise NotImplementedError()
