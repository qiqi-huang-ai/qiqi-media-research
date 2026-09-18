import json
from pathlib import Path

import pytest

from adapters.xiaohongshu import XiaohongshuAdapter, XiaohongshuAvailabilityError


FIXTURES = Path(__file__).parent / "fixtures" / "xiaohongshu"


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, params))
        return type("Response", (), {"data": self.payload})()


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_note_maps_collect_count_to_saves():
    post = XiaohongshuAdapter(FakeClient(load("note.json"))).get_post(note_id="note-1")
    assert post.post_id == "note-1"
    assert post.saves == 88
    assert post.views is None


def test_search_pagination_preserves_search_session():
    page = XiaohongshuAdapter(FakeClient(load("posts.json"))).search_posts("AI工具", page=1)
    state = json.loads(page.next_cursor)
    assert state["search_id"] == "search-test"
    assert state["page"] == 2


def test_comments_are_normalized():
    page = XiaohongshuAdapter(FakeClient(load("comments.json"))).get_comments(note_id="note-1")
    assert page.items[0].comment_id == "c-1"
    assert page.items[0].likes == 3


def test_upstream_service_error_is_not_an_empty_result():
    payload = {"code": 200, "data": {"success": False, "msg": "服务异常"}}
    with pytest.raises(XiaohongshuAvailabilityError):
        XiaohongshuAdapter(FakeClient(payload)).get_post(note_id="bad-id")


def test_detail_maps_live_nested_note_list_shape():
    note = load("note.json")["data"]["note"]
    payload = {"data": {"success": True, "data": [{"note_list": [note]}]}}
    post = XiaohongshuAdapter(FakeClient(payload)).get_post(note_id="note-1")
    assert post.post_id == "note-1"
