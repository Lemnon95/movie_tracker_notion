from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
from typing import Any, Callable, Mapping, Optional, Tuple, Union

import requests


Timeout = Union[float, Tuple[float, float]]
DEFAULT_TIMEOUT: Timeout = (5.0, 30.0)
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_RETRY_DELAY = 60.0


class HttpClientError(Exception):
    """Base error for failures at the shared HTTP transport boundary."""


class HttpTimeoutError(HttpClientError):
    """The remote service did not respond within the configured timeout."""


class HttpNetworkError(HttpClientError):
    """The request failed before a valid HTTP response was received."""


class HttpStatusError(HttpClientError):
    """The remote service returned an unsuccessful HTTP status."""

    def __init__(self, status_code: int, url: str, response_text: str = ""):
        self.status_code = status_code
        self.url = url
        self.response_text = response_text
        super().__init__(f"HTTP {status_code} returned by {url}")


class HttpDecodeError(HttpClientError):
    """A response expected to contain JSON could not be decoded."""


class HttpClient:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_retry_delay: float = DEFAULT_MAX_RETRY_DELAY,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if max_retry_delay < 0:
            raise ValueError("max_retry_delay must be non-negative")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self.sleeper = sleeper

    def _retry_delay(self, response: requests.Response, retry_number: int) -> float:
        headers = getattr(response, "headers", {})
        retry_after = (
            headers.get("Retry-After") if isinstance(headers, Mapping) else None
        )
        delay: Optional[float] = None
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                try:
                    retry_at = parsedate_to_datetime(str(retry_after))
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = None

        if delay is None:
            delay = float(2 ** (retry_number - 1))
        return min(max(delay, 0.0), self.max_retry_delay)

    def request(
        self,
        method: str,
        url: str,
        *,
        timeout: Optional[Timeout] = None,
        raise_for_status: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        effective_timeout = self.timeout if timeout is None else timeout
        retry_number = 0
        while True:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=effective_timeout,
                    **kwargs,
                )
            except requests.Timeout as exc:
                raise HttpTimeoutError(
                    f"Request timed out: {method.upper()} {url}"
                ) from exc
            except requests.RequestException as exc:
                raise HttpNetworkError(
                    f"Request failed: {method.upper()} {url}"
                ) from exc

            if response.status_code != 429 or retry_number >= self.max_retries:
                break
            retry_number += 1
            self.sleeper(self._retry_delay(response, retry_number))

        if raise_for_status and not 200 <= response.status_code < 400:
            raise HttpStatusError(
                status_code=response.status_code,
                url=getattr(response, "url", url) or url,
                response_text=getattr(response, "text", ""),
            )
        return response

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("HEAD", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", url, **kwargs)

    def parse_json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except (TypeError, ValueError) as exc:
            url = getattr(response, "url", "unknown URL") or "unknown URL"
            raise HttpDecodeError(f"Invalid JSON returned by {url}") from exc

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.parse_json(self.get(url, **kwargs))


default_http_client = HttpClient()
