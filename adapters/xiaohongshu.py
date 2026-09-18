"""TikHub Xiaohongshu App V2 adapter."""

from datetime import UTC, datetime
import json
from typing import Any

from adapters.base import Page
from scripts.models import Account, Comment, Post


IMAGE_NOTE = "/api/v1/xiaohongshu/app_v2/get_image_note_detail"
VIDEO_NOTE = "/api/v1/xiaohongshu/app_v2/get_video_note_detail"
PROFILE = "/api/v1/xiaohongshu/app_v2/get_user_info"
USER_POSTS = "/api/v1/xiaohongshu/app_v2/get_user_posted_notes"
COMMENTS = "/api/v1/xiaohongshu/app_v2/get_note_comments"
COMMENT_REPLIES = "/api/v1/xiaohongshu/app_v2/get_note_sub_comments"
SEARCH_NOTES = "/api/v1/xiaohongshu/app_v2/search_notes"
SEARCH_USERS = "/api/v1/xiaohongshu/app_v2/search_users"
TOPIC_INFO = "/api/v1/xiaohongshu/app_v2/get_topic_info"
TOPIC_FEED = "/api/v1/xiaohongshu/app_v2/get_topic_feed"


class XiaohongshuAvailabilityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _body(raw: dict[str, Any]) -> dict[str, Any]:
    body = raw.get("data", raw)
    if not isinstance(body, dict):
        raise XiaohongshuAvailabilityError("Xiaohongshu returned malformed data")
    message = body.get("msg") or body.get("message") or raw.get("message")
    if body.get("success") is False or message in {"服务异常", "数据异常"}:
        raise XiaohongshuAvailabilityError(f"Xiaohongshu data unavailable: {message or 'unknown'}")
    return body


def _items(body: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = body.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _post(item: dict[str, Any]) -> Post:
    card = item.get("note_card") if isinstance(item.get("note_card"), dict) else item
    note_id = str(card.get("note_id") or item.get("id") or card.get("id") or "")
    user = card.get("user") if isinstance(card.get("user"), dict) else {}
    stats = card.get("interact_info") if isinstance(card.get("interact_info"), dict) else {}
    title = card.get("title") or card.get("display_title")
    description = card.get("desc") or card.get("description")
    text = "\n".join(str(x) for x in (title, description) if x) or None
    return Post(
        platform="xiaohongshu",
        post_id=note_id,
        source_url=str(card.get("share_url") or f"https://www.xiaohongshu.com/explore/{note_id}"),
        author_id=_str(user.get("user_id") or user.get("userid")),
        author_name=_str(user.get("nickname") or user.get("nick_name")),
        text=text,
        likes=_int(stats.get("liked_count") or stats.get("like_count")),
        comments=_int(stats.get("comment_count")),
        shares=_int(stats.get("share_count")),
        saves=_int(stats.get("collected_count") or stats.get("collect_count")),
        collected_at=_now(),
    )


def _cursor(body: dict[str, Any], *, next_page: int | None = None) -> str | None:
    if not body.get("has_more"):
        return None
    state = {}
    for key in ("cursor", "search_id"):
        if body.get(key) is not None:
            state[key] = body[key]
    if next_page is not None:
        state["page"] = next_page
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


def _decode(cursor: str | None) -> dict[str, Any]:
    if not cursor:
        return {}
    try:
        value = json.loads(cursor)
    except json.JSONDecodeError as error:
        raise ValueError("invalid Xiaohongshu cursor") from error
    if not isinstance(value, dict):
        raise ValueError("invalid Xiaohongshu cursor")
    return value


def _one_of(first: Any, second: Any, names: str) -> None:
    if (first is None) == (second is None):
        raise ValueError(f"provide exactly one of {names}")


class XiaohongshuAdapter:
    def __init__(self, client: Any):
        self.client = client

    def search_posts(self, keyword: str, *, page: int = 1, cursor: str | None = None) -> Page[Post]:
        state = _decode(cursor)
        page = int(state.get("page", page))
        params = {"keyword": keyword, "page": page}
        if state.get("search_id"):
            params["search_id"] = state["search_id"]
        raw = self.client.get(SEARCH_NOTES, params).data
        body = _body(raw)
        return Page([_post(x) for x in _items(body, "items", "notes")], _cursor(body, next_page=page + 1), bool(body.get("has_more")), raw)

    def search_accounts(self, keyword: str, *, page: int = 1, cursor: str | None = None) -> Page[Account]:
        state = _decode(cursor)
        page = int(state.get("page", page))
        params = {"keyword": keyword, "page": page, **({"search_id": state["search_id"]} if state.get("search_id") else {})}
        raw = self.client.get(SEARCH_USERS, params).data
        body = _body(raw)
        records = [self._account(x) for x in _items(body, "items", "users")]
        return Page(records, _cursor(body, next_page=page + 1), bool(body.get("has_more")), raw)

    def get_account(self, *, user_id: str | None = None, share_text: str | None = None) -> Account:
        _one_of(user_id, share_text, "user_id or share_text")
        params = {"user_id": user_id} if user_id else {"share_text": share_text}
        raw = self.client.get(PROFILE, params).data
        body = _body(raw)
        return self._account(body.get("user_info") or body.get("user") or body)

    def get_account_posts(self, *, user_id: str | None = None, share_text: str | None = None, cursor: str = "") -> Page[Post]:
        _one_of(user_id, share_text, "user_id or share_text")
        params = {"cursor": cursor, **({"user_id": user_id} if user_id else {"share_text": share_text})}
        raw = self.client.get(USER_POSTS, params).data
        body = _body(raw)
        return Page([_post(x) for x in _items(body, "notes", "items")], _cursor(body), bool(body.get("has_more")), raw)

    def get_post(self, *, note_id: str | None = None, share_text: str | None = None, video: bool = False) -> Post:
        _one_of(note_id, share_text, "note_id or share_text")
        params = {"note_id": note_id} if note_id else {"share_text": share_text}
        raw = self.client.get(VIDEO_NOTE if video else IMAGE_NOTE, params).data
        body = _body(raw)
        note = body.get("note") or body.get("note_detail")
        if not isinstance(note, dict):
            raise XiaohongshuAvailabilityError("Xiaohongshu note is unavailable")
        return _post(note)

    def get_comments(self, *, note_id: str | None = None, share_text: str | None = None, cursor: str = "", index: int = 0) -> Page[Comment]:
        _one_of(note_id, share_text, "note_id or share_text")
        params = {"cursor": cursor, "index": index, **({"note_id": note_id} if note_id else {"share_text": share_text})}
        raw = self.client.get(COMMENTS, params).data
        body = _body(raw)
        records = [self._comment(x, note_id or "") for x in _items(body, "comments", "items")]
        return Page(records, _cursor(body), bool(body.get("has_more")), raw)

    def get_topic_feed(self, page_id: str, *, cursor: str | None = None) -> Page[Post]:
        state = _decode(cursor)
        raw = self.client.get(TOPIC_FEED, {"page_id": page_id, **state}).data
        body = _body(raw)
        return Page([_post(x) for x in _items(body, "notes", "items")], _cursor(body), bool(body.get("has_more")), raw)

    @staticmethod
    def _account(item: dict[str, Any]) -> Account:
        user_id = str(item.get("user_id") or item.get("userid") or item.get("id") or "")
        return Account(platform="xiaohongshu", account_id=user_id, source_url=str(item.get("share_url") or f"https://www.xiaohongshu.com/user/profile/{user_id}"), name=_str(item.get("nickname") or item.get("nick_name")), bio=_str(item.get("desc") or item.get("description")), followers=_int(item.get("fans") or item.get("fans_count")), following=_int(item.get("follows") or item.get("following_count")), posts=_int(item.get("notes") or item.get("note_count")), likes_received=_int(item.get("liked") or item.get("liked_count")), collected_at=_now())

    @staticmethod
    def _comment(item: dict[str, Any], fallback_note_id: str) -> Comment:
        user = item.get("user_info") if isinstance(item.get("user_info"), dict) else {}
        note_id = str(item.get("note_id") or fallback_note_id)
        return Comment(platform="xiaohongshu", comment_id=str(item.get("id") or item.get("comment_id") or ""), post_id=note_id, source_url=f"https://www.xiaohongshu.com/explore/{note_id}", author_id=_str(user.get("user_id")), author_name=_str(user.get("nickname")), text=_str(item.get("content")), likes=_int(item.get("like_count")), reply_count=_int(item.get("sub_comment_count")), collected_at=_now())
