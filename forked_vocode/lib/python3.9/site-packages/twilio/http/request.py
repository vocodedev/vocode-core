from enum import Enum
from typing import Any, Dict, Tuple, Union
from urllib.parse import urlencode


class Match(Enum):
    ANY = "*"


class Request(object):
    """
    An HTTP request.
    """

    def __init__(
        self,
        method: Union[str, Match] = Match.ANY,
        url: Union[str, Match] = Match.ANY,
        auth: Union[Tuple[str, str], Match] = Match.ANY,
        params: Union[Dict[str, str], Match] = Match.ANY,
        data: Union[Dict[str, str], Match] = Match.ANY,
        headers: Union[Dict[str, str], Match] = Match.ANY,
        **kwargs: Any
    ):
        self.method = method
        if method and method is not Match.ANY:
            self.method = method.upper()
        self.url = url
        self.auth = auth
        self.params = params
        self.data = data
        self.headers = headers

    @classmethod
    def attribute_equal(cls, lhs, rhs) -> bool:
        if lhs == Match.ANY or rhs == Match.ANY:
            # ANY matches everything
            return True

        lhs = lhs or None
        rhs = rhs or None

        return lhs == rhs

    def __eq__(self, other) -> bool:
        if not isinstance(other, Request):
            return False

        return (
            self.attribute_equal(self.method, other.method)
            and self.attribute_equal(self.url, other.url)
            and self.attribute_equal(self.auth, other.auth)
            and self.attribute_equal(self.params, other.params)
            and self.attribute_equal(self.data, other.data)
            and self.attribute_equal(self.headers, other.headers)
        )

    def __str__(self) -> str:
        auth = ""
        if self.auth and self.auth != Match.ANY:
            auth = "{} ".format(self.auth)

        params = ""
        if self.params and self.params != Match.ANY:
            params = "?{}".format(urlencode(self.params, doseq=True))

        data = ""
        if self.data and self.data != Match.ANY:
            if self.method == "GET":
                data = "\n -G"
            data += "\n{}".format(
                "\n".join(' -d "{}={}"'.format(k, v) for k, v in self.data.items())
            )

        headers = ""
        if self.headers and self.headers != Match.ANY:
            headers = "\n{}".format(
                "\n".join(' -H "{}: {}"'.format(k, v) for k, v in self.headers.items())
            )

        return "{auth}{method} {url}{params}{data}{headers}".format(
            auth=auth,
            method=self.method,
            url=self.url,
            params=params,
            data=data,
            headers=headers,
        )

    def __repr__(self) -> str:
        return str(self)
