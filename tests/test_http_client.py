from unittest.mock import Mock, call

import pytest
import requests

from movie_tracker.http_client import (
    HttpClient,
    HttpDecodeError,
    HttpNetworkError,
    HttpStatusError,
    HttpTimeoutError,
)


def response(
    status_code=200,
    *,
    url="https://example.test/data",
    text="",
    json_data=None,
    headers=None,
):
    result = Mock(status_code=status_code, url=url, text=text, headers=headers or {})
    if json_data is not None:
        result.json.return_value = json_data
    return result


def test_client_reuses_session_and_applies_default_timeout():
    session = Mock()
    expected = response()
    session.request.return_value = expected
    client = HttpClient(session=session, timeout=(2, 9))

    actual = client.post("https://example.test/data", json={"value": 1})

    assert actual is expected
    session.request.assert_called_once_with(
        method="POST",
        url="https://example.test/data",
        timeout=(2, 9),
        json={"value": 1},
    )


def test_client_allows_timeout_override():
    session = Mock()
    session.request.return_value = response()

    HttpClient(session=session).get("https://example.test/data", timeout=120)

    assert session.request.call_args.kwargs["timeout"] == 120


def test_client_wraps_timeout_errors():
    session = Mock()
    session.request.side_effect = requests.Timeout("too slow")

    with pytest.raises(HttpTimeoutError) as error:
        HttpClient(session=session).get("https://example.test/data")

    assert isinstance(error.value.__cause__, requests.Timeout)


def test_client_wraps_network_errors():
    session = Mock()
    session.request.side_effect = requests.ConnectionError("offline")

    with pytest.raises(HttpNetworkError) as error:
        HttpClient(session=session).get("https://example.test/data")

    assert isinstance(error.value.__cause__, requests.ConnectionError)


def test_client_exposes_http_status_details():
    session = Mock()
    session.request.return_value = response(
        401, url="https://example.test/private", text="invalid token"
    )

    with pytest.raises(HttpStatusError) as error:
        HttpClient(session=session).get("https://example.test/private")

    assert error.value.status_code == 401
    assert error.value.url == "https://example.test/private"
    assert error.value.response_text == "invalid token"


def test_client_can_return_unsuccessful_response_when_service_needs_it():
    session = Mock()
    expected = response(404)
    session.request.return_value = expected

    actual = HttpClient(session=session).head(
        "https://example.test/missing", raise_for_status=False
    )

    assert actual is expected


def test_client_parses_json():
    session = Mock()
    session.request.return_value = response(json_data={"ok": True})

    assert HttpClient(session=session).get_json("https://example.test/data") == {
        "ok": True
    }


def test_client_wraps_invalid_json():
    session = Mock()
    invalid = response()
    invalid.json.side_effect = ValueError("not json")
    session.request.return_value = invalid

    with pytest.raises(HttpDecodeError) as error:
        HttpClient(session=session).get_json("https://example.test/data")

    assert isinstance(error.value.__cause__, ValueError)


def test_client_retries_rate_limit_and_honors_retry_after():
    session = Mock()
    session.request.side_effect = [
        response(429, headers={"Retry-After": "3"}),
        response(json_data={"ok": True}),
    ]
    sleeper = Mock()
    client = HttpClient(session=session, sleeper=sleeper)

    assert client.get_json("https://example.test/data") == {"ok": True}

    assert session.request.call_count == 2
    sleeper.assert_called_once_with(3.0)


def test_client_uses_bounded_exponential_backoff_without_valid_header():
    session = Mock()
    session.request.side_effect = [
        response(429),
        response(429, headers={"Retry-After": "not-a-delay"}),
        response(),
    ]
    sleeper = Mock()
    client = HttpClient(session=session, sleeper=sleeper, max_retry_delay=1.5)

    client.get("https://example.test/data")

    assert sleeper.call_args_list == [call(1.0), call(1.5)]


def test_client_caps_retry_after_and_accepts_http_date():
    session = Mock()
    session.request.side_effect = [
        response(429, headers={"Retry-After": "999"}),
        response(429, headers={"Retry-After": "Thu, 01 Jan 1970 00:00:00 GMT"}),
        response(),
    ]
    sleeper = Mock()

    HttpClient(session=session, sleeper=sleeper, max_retry_delay=5).get(
        "https://example.test/data"
    )

    assert sleeper.call_args_list == [call(5), call(0.0)]


def test_client_raises_after_rate_limit_retry_budget_is_exhausted():
    session = Mock()
    session.request.side_effect = [response(429), response(429), response(429)]
    sleeper = Mock()

    with pytest.raises(HttpStatusError) as error:
        HttpClient(session=session, sleeper=sleeper).get("https://example.test/data")

    assert error.value.status_code == 429
    assert session.request.call_count == 3
    assert sleeper.call_count == 2


def test_client_does_not_retry_other_http_errors():
    session = Mock()
    session.request.return_value = response(503)
    sleeper = Mock()

    with pytest.raises(HttpStatusError):
        HttpClient(session=session, sleeper=sleeper).get("https://example.test/data")

    session.request.assert_called_once()
    sleeper.assert_not_called()


@pytest.mark.parametrize("max_retries", [-1, -10])
def test_client_rejects_negative_retry_budget(max_retries):
    with pytest.raises(ValueError, match="max_retries"):
        HttpClient(max_retries=max_retries)


def test_client_rejects_negative_retry_delay_cap():
    with pytest.raises(ValueError, match="max_retry_delay"):
        HttpClient(max_retry_delay=-0.1)


def test_client_retries_rate_limit_even_when_status_errors_are_disabled():
    session = Mock()
    session.request.side_effect = [response(429), response(404)]
    sleeper = Mock()

    actual = HttpClient(session=session, sleeper=sleeper).head(
        "https://example.test/image", raise_for_status=False
    )

    assert actual.status_code == 404
    assert session.request.call_count == 2
