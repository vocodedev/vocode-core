import asyncio
import logging
import sys
from abc import abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from aiohttp import ClientResponse, ClientSession, hdrs
from aiohttp.typedefs import StrOrURL
from yarl import URL as YARL_URL

from .retry_options import ExponentialRetry, RetryOptionsBase

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol


class _Logger(Protocol):
    """
    _Logger defines which methods logger object should have
    """

    @abstractmethod
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: pass

    @abstractmethod
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: pass

    @abstractmethod
    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None: pass


# url itself or list of urls for changing between retries
_RAW_URL_TYPE = Union[StrOrURL, YARL_URL]
_URL_TYPE = Union[_RAW_URL_TYPE, List[_RAW_URL_TYPE], Tuple[_RAW_URL_TYPE, ...]]
_LoggerType = Union[_Logger, logging.Logger]

RequestFunc = Callable[..., Awaitable[ClientResponse]]


@dataclass
class RequestParams:
    method: str
    url: _RAW_URL_TYPE
    headers: Optional[Dict[str, Any]] = None
    trace_request_ctx: Optional[Dict[str, Any]] = None
    kwargs: Optional[Dict[str, Any]] = None


class _RequestContext:
    def __init__(
        self,
        request_func: RequestFunc,
        params_list: List[RequestParams],
        logger: _LoggerType,
        retry_options: RetryOptionsBase,
        raise_for_status: bool = False,
    ) -> None:
        assert len(params_list) > 0

        self._request_func = request_func
        self._params_list = params_list
        self._logger = logger
        self._retry_options = retry_options
        self._raise_for_status = raise_for_status

        self._response: Optional[ClientResponse] = None

    def _is_status_code_ok(self, code: int) -> bool:
        if code >= 500 and self._retry_options.retry_all_server_errors:
            return False
        return code not in self._retry_options.statuses

    async def _do_request(self) -> ClientResponse:
        current_attempt = 0
        while True:
            self._logger.debug(f"Attempt {current_attempt+1} out of {self._retry_options.attempts}")

            current_attempt += 1
            try:
                try:
                    params = self._params_list[current_attempt - 1]
                except IndexError:
                    params = self._params_list[-1]

                response: ClientResponse = await self._request_func(
                    params.method,
                    params.url,
                    headers=params.headers,
                    trace_request_ctx={
                        'current_attempt': current_attempt,
                        **(params.trace_request_ctx or {}),
                    },
                    **(params.kwargs or {}),
                )

                if self._is_status_code_ok(response.status) or current_attempt == self._retry_options.attempts:
                    if self._raise_for_status:
                        response.raise_for_status()

                    if self._retry_options.evaluate_response_callback is not None:
                        try:
                            is_response_correct = await self._retry_options.evaluate_response_callback(response)
                        except Exception:
                            self._logger.exception('while evaluating response an exception occurred')
                            is_response_correct = False
                    else:
                        is_response_correct = True

                    if is_response_correct or current_attempt == self._retry_options.attempts:
                        self._response = response
                        return response
                    else:
                        self._logger.debug(f"Retrying after evaluate response callback check")
                else:
                    self._logger.debug(f"Retrying after response code: {response.status}")
                retry_wait = self._retry_options.get_timeout(attempt=current_attempt, response=response)
            except Exception as e:
                if current_attempt >= self._retry_options.attempts:
                    raise e

                is_exc_valid = any([isinstance(e, exc) for exc in self._retry_options.exceptions])
                if not is_exc_valid:
                    raise e

                self._logger.debug(f"Retrying after exception: {repr(e)}")
                retry_wait = self._retry_options.get_timeout(attempt=current_attempt, response=None)

            await asyncio.sleep(retry_wait)

    def __await__(self) -> Generator[Any, None, ClientResponse]:
        return self.__aenter__().__await__()

    async def __aenter__(self) -> ClientResponse:
        return await self._do_request()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._response is not None:
            if not self._response.closed:
                self._response.close()


def _url_to_urls(url: _URL_TYPE) -> Tuple[StrOrURL, ...]:
    if isinstance(url, str) or isinstance(url, YARL_URL):
        return (url,)

    if isinstance(url, list):
        urls = tuple(url)
    elif isinstance(url, tuple):
        urls = url
    else:
        raise ValueError("you can pass url only by str or list/tuple")

    if len(urls) == 0:
        raise ValueError("you can pass url by str or list/tuple with attempts count size")

    return urls


class RetryClient:
    def __init__(
        self,
        client_session: Optional[ClientSession] = None,
        logger: Optional[_LoggerType] = None,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if client_session is not None:
            client = client_session
            closed = None
        else:
            client = ClientSession(*args, **kwargs)
            closed = False

        self._client = client
        self._closed = closed

        self._logger: _LoggerType = logger or logging.getLogger("aiohttp_retry")
        self._retry_options: RetryOptionsBase = retry_options or ExponentialRetry()
        self._raise_for_status = raise_for_status

    @property
    def retry_options(self) -> RetryOptionsBase:
        return self._retry_options

    def requests(
        self,
        params_list: List[RequestParams],
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
    ) -> _RequestContext:
        return self._make_requests(
            params_list=params_list,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
        )

    def request(
        self,
        method: str,
        url: StrOrURL,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=method,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def get(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_GET,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def options(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_OPTIONS,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def head(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None, **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_HEAD,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def post(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_POST,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def put(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_PUT,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def patch(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_PATCH,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    def delete(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        return self._make_request(
            method=hdrs.METH_DELETE,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    def _make_request(
        self,
        method: str,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> _RequestContext:
        url_list = _url_to_urls(url)
        params_list = [RequestParams(
            method=method,
            url=url,
            headers=kwargs.pop('headers', {}),
            trace_request_ctx=kwargs.pop('trace_request_ctx', None),
            kwargs=kwargs,
        ) for url in url_list]

        return self._make_requests(
            params_list=params_list,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
        )

    def _make_requests(
        self,
        params_list: List[RequestParams],
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
    ) -> _RequestContext:
        if retry_options is None:
            retry_options = self._retry_options
        if raise_for_status is None:
            raise_for_status = self._raise_for_status
        return _RequestContext(
            request_func=self._client.request,
            params_list=params_list,
            logger=self._logger,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
        )

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    def __del__(self) -> None:
        if getattr(self, '_closed', None) is None:
            # in case object was not initialized (__init__ raised an exception)
            return

        if not self._closed:
            self._logger.warning("Aiohttp retry client was not closed")
