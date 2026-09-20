import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from scripts.api_client import MissingApiKey, TikHubClient, TikHubError


class FakeHeaders(dict):
    def get_content_charset(self):
        return "utf-8"


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = json.dumps(payload).encode()
        self.status = status
        self.headers = FakeHeaders(headers or {})

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def http_error(status, payload=b"{}", headers=None):
    return urllib.error.HTTPError(
        "https://api.tikhub.io/x",
        status,
        "error",
        headers or {},
        io.BytesIO(payload),
    )


def test_missing_key_stops_before_network(monkeypatch):
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)
    with pytest.raises(MissingApiKey):
        TikHubClient()


def test_get_sends_bearer_and_parses_object_without_exposing_key(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    response = FakeResponse({"code": 200, "data": {"ok": True}})
    with patch("urllib.request.urlopen", return_value=response) as mocked:
        result = TikHubClient().get("/api/test", {"q": "中文"})
    request = mocked.call_args.args[0]
    assert request.headers["Authorization"] == "Bearer secret-value"
    assert "%E4%B8%AD%E6%96%87" in request.full_url
    assert result.data == {"code": 200, "data": {"ok": True}}
    assert "secret-value" not in repr(result)


def test_401_is_not_retried(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    with patch("urllib.request.urlopen", side_effect=http_error(401)) as mocked:
        with pytest.raises(TikHubError) as caught:
            TikHubClient().get("/x", {})
    assert mocked.call_count == 1
    assert caught.value.status == 401
    assert caught.value.retryable is False


def test_cloudflare_403_is_not_retried_and_is_explicit(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    blocked = http_error(403, b"<html>Cloudflare Error 1010</html>")
    with patch("urllib.request.urlopen", side_effect=blocked) as mocked:
        with pytest.raises(TikHubError, match="Cloudflare/WAF") as caught:
            TikHubClient().get("/x", {})
    assert mocked.call_count == 1
    assert caught.value.status == 403
    assert caught.value.retryable is False


def test_500_retries_only_to_configured_limit(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    with patch("urllib.request.urlopen", side_effect=http_error(500)) as mocked:
        with patch("time.sleep"):
            with pytest.raises(TikHubError) as caught:
                TikHubClient(max_retries=2).get("/x", {})
    assert mocked.call_count == 3
    assert caught.value.retryable is True


def test_non_object_json_is_rejected(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    with patch("urllib.request.urlopen", return_value=FakeResponse([1, 2])):
        with pytest.raises(TikHubError, match="non-object JSON"):
            TikHubClient().get("/x", {})
