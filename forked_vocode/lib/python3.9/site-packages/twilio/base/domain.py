from typing import Dict, Optional, Tuple
from twilio.http.response import Response
from twilio.rest import Client


class Domain(object):
    """
    This represents at Twilio API subdomain.

    Like, `api.twilio.com` or `lookups.twilio.com'.
    """

    def __init__(self, twilio: Client, base_url: str):
        self.twilio = twilio
        self.base_url = base_url

    def absolute_url(self, uri: str) -> str:
        """
        Converts a relative `uri` to an absolute url.
        :param string uri: The relative uri to make absolute.
        :return: An absolute url (based off this domain)
        """
        return "{}/{}".format(self.base_url.strip("/"), uri.strip("/"))

    def request(
        self,
        method: str,
        uri: str,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = False,
    ) -> Response:
        """
        Makes an HTTP request to this domain.
        :param method: The HTTP method.
        :param uri: The HTTP uri.
        :param params: Query parameters.
        :param data: The request body.
        :param headers: The HTTP headers.
        :param auth: Basic auth tuple of (username, password)
        :param timeout: The request timeout.
        :param allow_redirects: True if the client should follow HTTP
        redirects.
        """
        url = self.absolute_url(uri)
        return self.twilio.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            auth=auth,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    async def request_async(
        self,
        method: str,
        uri: str,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = False,
    ) -> Response:
        """
        Makes an asynchronous HTTP request to this domain.
        :param method: The HTTP method.
        :param uri: The HTTP uri.
        :param params: Query parameters.
        :param data: The request body.
        :param headers: The HTTP headers.
        :param auth: Basic auth tuple of (username, password)
        :param timeout: The request timeout.
        :param allow_redirects: True if the client should follow HTTP
        redirects.
        """
        url = self.absolute_url(uri)
        return await self.twilio.request_async(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            auth=auth,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )
