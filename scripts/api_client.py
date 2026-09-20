"""Small credential-safe client for TikHub's REST API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    data: dict[str, Any]
    headers: dict[str, str]


class TikHubError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class MissingApiKey(TikHubError):
    pass


class TikHubClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.tikhub.io",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        api_key = os.getenv("TIKHUB_API_KEY", "").strip()
        if not api_key:
            raise MissingApiKey(
                "TIKHUB_API_KEY is missing; configure it in the local environment"
            )
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def get(self, path: str, params: Mapping[str, object]) -> ApiResponse:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "User-Agent": "qiqi-media-research/0.1.0",
            },
            method="GET",
        )

        return self._open(request)

    def post(self, path: str, payload: Mapping[str, object]) -> ApiResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "qiqi-media-research/0.1.0",
            },
            method="POST",
        )
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> ApiResponse:

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = self._decode_json(response.read())
                    return ApiResponse(
                        status=getattr(response, "status", 200),
                        data=payload,
                        headers=dict(response.headers.items()),
                    )
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt == self.max_retries:
                    if exc.code == 403 and self._is_cloudflare_waf(exc):
                        raise TikHubError(
                            "TikHub HTTP 403 (Cloudflare/WAF blocked this request; "
                            "end this task and start a new task later)",
                            status=403,
                            retryable=False,
                        ) from exc
                    raise TikHubError(
                        f"TikHub HTTP {exc.code}",
                        status=exc.code,
                        retryable=retryable,
                    ) from exc
                time.sleep(self._retry_delay(attempt, exc.headers))
            except urllib.error.URLError as exc:
                if attempt == self.max_retries:
                    raise TikHubError(
                        "TikHub network request failed", retryable=True
                    ) from exc
                time.sleep(self._retry_delay(attempt, {}))

        raise AssertionError("retry loop exhausted without returning or raising")

    @staticmethod
    def _decode_json(body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TikHubError("TikHub returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TikHubError("TikHub returned non-object JSON")
        return payload

    @staticmethod
    def _is_cloudflare_waf(exc: urllib.error.HTTPError) -> bool:
        """Recognize a block page without surfacing its raw body to users."""
        try:
            body = exc.read(4096).decode("utf-8", errors="replace").lower()
        except (AttributeError, OSError):
            body = ""
        markers = ("cloudflare", "error 1010", "error 1020", "waf")
        return any(marker in body for marker in markers)

    @staticmethod
    def _retry_delay(attempt: int, headers: Mapping[str, object]) -> float:
        retry_after = headers.get("Retry-After") if headers else None
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), 10.0)
            except (TypeError, ValueError):
                pass
        return min(0.5 * (2**attempt), 10.0)
