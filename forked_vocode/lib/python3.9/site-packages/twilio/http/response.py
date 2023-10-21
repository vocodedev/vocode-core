from typing import Any, Optional


class Response(object):
    def __init__(
        self,
        status_code: int,
        text: str,
        headers: Optional[Any] = None,
    ):
        self.content = text
        self.headers = headers
        self.cached = False
        self.status_code = status_code
        self.ok = self.status_code < 400

    @property
    def text(self) -> str:
        return self.content

    def __repr__(self) -> str:
        return "HTTP {} {}".format(self.status_code, self.content)
