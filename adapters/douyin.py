"""TikHub Douyin App V3 and Search API adapter."""

from datetime import UTC, datetime
from typing import Any, Iterable

from adapters.base import Page
from scripts.models import Account, Comment, Post, TrendItem


VIDEO = "/api/v1/douyin/app/v3/fetch_one_video"
VIDEO_BY_URL = "/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
VIDEO_STATS = "/api/v1/douyin/app/v3/fetch_video_statistics"
PROFILE = "/api/v1/douyin/app/v3/handler_user_profile"
USER_POSTS = "/api/v1/douyin/app/v3/fetch_user_post_videos"
COMMENTS = "/api/v1/douyin/app/v3/fetch_video_comments"
COMMENT_REPLIES = "/api/v1/douyin/app/v3/fetch_video_comment_replies"
HOT_SEARCH = "/api/v1/douyin/app/v3/fetch_hot_search_list"
VIDEO_SEARCH = "/api/v1/douyin/search/fetch_video_search_v2"
USER_SEARCH = "/api/v1/douyin/search/fetch_user_search_v2"


class DouyinAvailabilityError(RuntimeError):
    """The requested Douyin entity is filtered, private, deleted, or unavailable."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> str | None:
    number = _int(value)
    if number is None:
        return None
    try:
        return datetime.fromtimestamp(number, UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _body(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data", raw)
    return data if isinstance(data, dict) else {}


def _list(body: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = body.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    nested = body.get("data")
    if isinstance(nested, dict):
        return _list(nested, *keys)
    if isinstance(nested, list):
        return [item for item in nested if isinstance(item, dict)]
    business = body.get("business_data")
    if isinstance(business, list):
        results = []
        for item in business:
            if not isinstance(item, dict):
                continue
            value = item.get("data")
            if isinstance(value, dict) and isinstance(value.get("aweme_info"), dict):
                results.append(value)
        return results
    return []


def _cursor(body: dict[str, Any]) -> str | None:
    for key in ("max_cursor", "cursor", "offset"):
        if body.get(key) is not None:
            return str(body[key])
    nested = body.get("data")
    if isinstance(nested, dict):
        return _cursor(nested)
    config = body.get("business_config")
    if isinstance(config, dict) and isinstance(config.get("next_page"), dict):
        value = config["next_page"].get("cursor")
        return str(value) if value is not None else None
    return None


def _has_more(body: dict[str, Any]) -> bool:
    value = body.get("has_more")
    if value is None and isinstance(body.get("data"), dict):
        return _has_more(body["data"])
    if value is None and isinstance(body.get("business_config"), dict):
        value = body["business_config"].get("has_more")
    return value is True or value == 1 or value == "1"


def _post(item: dict[str, Any]) -> Post:
    if isinstance(item.get("aweme_info"), dict):
        item = item["aweme_info"]
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    post_id = str(item.get("aweme_id") or item.get("id") or "")
    duration_ms = _float(item.get("duration"))
    return Post(
        platform="douyin",
        post_id=post_id,
        source_url=str(item.get("share_url") or f"https://www.douyin.com/video/{post_id}"),
        author_id=_string(author.get("sec_uid") or author.get("uid")),
        author_name=_string(author.get("nickname")),
        text=_string(item.get("desc")),
        published_at=_timestamp(item.get("create_time")),
        views=_int(stats.get("play_count")),
        likes=_int(stats.get("digg_count")),
        comments=_int(stats.get("comment_count")),
        shares=_int(stats.get("share_count")),
        saves=_int(stats.get("collect_count")),
        followers=_int(author.get("follower_count")),
        duration_sec=duration_ms / 1000 if duration_ms is not None else None,
        collected_at=_now(),
    )


def _string(value: Any) -> str | None:
    return None if value is None else str(value)


class DouyinAdapter:
    def __init__(self, client: Any):
        self.client = client
        self.last_raw: dict[str, Any] | None = None

    def search_posts(self, keyword: str, *, cursor: str = "0") -> Page[Post]:
        raw = self.client.post(VIDEO_SEARCH, {
            "keyword": keyword, "cursor": int(cursor), "sort_type": "0",
            "publish_time": "0", "filter_duration": "0", "content_type": "0",
            "search_id": "", "backtrace": "",
        }).data
        body = _body(raw)
        return Page([_post(x) for x in _list(body, "aweme_list")], _cursor(body), _has_more(body), raw)

    def search_accounts(self, keyword: str, *, cursor: str = "0") -> Page[Account]:
        raw = self.client.post(USER_SEARCH, {"keyword": keyword, "cursor": int(cursor)}).data
        body = _body(raw)
        records = []
        for item in _list(body, "user_list", "users"):
            user = item.get("user_info") if isinstance(item.get("user_info"), dict) else item
            account_id = str(user.get("sec_uid") or user.get("uid") or "")
            records.append(Account(platform="douyin", account_id=account_id, source_url=f"https://www.douyin.com/user/{account_id}", name=_string(user.get("nickname")), bio=_string(user.get("signature")), followers=_int(user.get("follower_count")), following=_int(user.get("following_count")), posts=_int(user.get("aweme_count")), likes_received=_int(user.get("total_favorited")), collected_at=_now()))
        return Page(records, _cursor(body), _has_more(body), raw)

    def get_account(self, sec_user_id: str) -> Account:
        raw = self.client.get(PROFILE, {"sec_user_id": sec_user_id}).data
        self.last_raw = raw
        body = _body(raw)
        user = body.get("user") or body.get("user_info") or body
        if not isinstance(user, dict):
            user = {}
        return Account(
            platform="douyin",
            account_id=str(user.get("sec_uid") or sec_user_id),
            source_url=f"https://www.douyin.com/user/{user.get('sec_uid') or sec_user_id}",
            name=_string(user.get("nickname")),
            bio=_string(user.get("signature")),
            followers=_int(user.get("follower_count")),
            following=_int(user.get("following_count")),
            posts=_int(user.get("aweme_count")),
            likes_received=_int(user.get("total_favorited")),
            collected_at=_now(),
        )

    def get_account_posts(self, sec_user_id: str, *, cursor: str = "0", count: int = 20) -> Page[Post]:
        raw = self.client.get(
            USER_POSTS,
            {"sec_user_id": sec_user_id, "max_cursor": cursor, "count": count},
        ).data
        body = _body(raw)
        return Page([_post(x) for x in _list(body, "aweme_list")], _cursor(body), _has_more(body), raw)

    def get_post(self, *, aweme_id: str | None = None, share_url: str | None = None) -> Post:
        if (aweme_id is None) == (share_url is None):
            raise ValueError("provide exactly one of aweme_id or share_url")
        path = VIDEO if aweme_id is not None else VIDEO_BY_URL
        params = {"aweme_id": aweme_id} if aweme_id is not None else {"share_url": share_url}
        raw = self.client.get(path, params).data
        self.last_raw = raw
        body = _body(raw)
        detail = body.get("aweme_detail") or body.get("aweme")
        if not isinstance(detail, dict):
            reason = body.get("filter_detail") or body.get("status_msg") or "unavailable"
            raise DouyinAvailabilityError(f"Douyin post is unavailable: {reason}")
        return _post(detail)

    def get_comments(self, aweme_id: str, *, cursor: str = "0", count: int = 20) -> Page[Comment]:
        raw = self.client.get(
            COMMENTS, {"aweme_id": aweme_id, "cursor": cursor, "count": count}
        ).data
        body = _body(raw)
        items = [self._comment(item, aweme_id) for item in _list(body, "comments")]
        return Page(items, _cursor(body), _has_more(body), raw)

    def get_trends(self) -> Page[TrendItem]:
        raw = self.client.get(HOT_SEARCH, {}).data
        body = _body(raw)
        source = _list(body, "word_list", "data")
        items = []
        for index, item in enumerate(source, start=1):
            title = str(item.get("word") or item.get("sentence") or item.get("title") or "")
            trend_id = str(item.get("word_id") or item.get("sentence_id") or title)
            items.append(
                TrendItem(
                    platform="douyin",
                    trend_id=trend_id,
                    title=title,
                    source_url=str(item.get("url") or "https://www.douyin.com/hot"),
                    rank=_int(item.get("position")) or index,
                    score=_float(item.get("hot_value")),
                    category=_string(item.get("label_name")),
                    collected_at=_now(),
                )
            )
        return Page(items, None, False, raw)

    @staticmethod
    def _comment(item: dict[str, Any], aweme_id: str) -> Comment:
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        post_id = str(item.get("aweme_id") or aweme_id)
        return Comment(
            platform="douyin",
            comment_id=str(item.get("cid") or item.get("comment_id") or ""),
            post_id=post_id,
            source_url=f"https://www.douyin.com/video/{post_id}",
            author_id=_string(user.get("sec_uid") or user.get("uid")),
            author_name=_string(user.get("nickname")),
            text=_string(item.get("text")),
            published_at=_timestamp(item.get("create_time")),
            likes=_int(item.get("digg_count")),
            reply_count=_int(item.get("reply_comment_total")),
            parent_comment_id=_string(item.get("reply_id")),
            collected_at=_now(),
        )
