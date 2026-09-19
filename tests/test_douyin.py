import json
from pathlib import Path

import pytest

from adapters.douyin import DouyinAdapter, DouyinAvailabilityError


FIXTURES = Path(__file__).parent / "fixtures" / "douyin"


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, params))
        return type("Response", (), {"data": self.payload})()

    def post(self, path, params):
        return self.get(path, params)


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_get_post_maps_statistics_without_guessing():
    client = FakeClient(load("video.json"))
    post = DouyinAdapter(client).get_post(aweme_id="7350810998023949599")
    assert post.post_id == "7350810998023949599"
    assert post.likes == 214000
    assert post.saves == 22100
    assert post.views == 3120000
    assert post.views_source == "detail"
    assert client.calls[0][0] == "/api/v1/douyin/app/v3/fetch_one_video"


def test_account_posts_carries_next_cursor_and_keeps_missing_view_null():
    page = DouyinAdapter(FakeClient(load("posts.json"))).get_account_posts(
        "sec-1", cursor="0"
    )
    assert page.next_cursor == "20"
    assert page.has_more is True
    assert page.items[1].views is None


def test_comments_are_mapped_with_pagination():
    page = DouyinAdapter(FakeClient(load("comments.json"))).get_comments("post-1")
    assert page.items[0].comment_id == "comment-1"
    assert page.items[0].reply_count == 2
    assert page.next_cursor == "20"


def test_get_post_requires_exactly_one_identifier():
    adapter = DouyinAdapter(FakeClient(load("video.json")))
    with pytest.raises(ValueError):
        adapter.get_post()
    with pytest.raises(ValueError):
        adapter.get_post(aweme_id="1", share_url="https://example.test/1")


def test_filtered_response_is_not_treated_as_empty_result():
    payload = {"code": 200, "data": {"filter_detail": {"detail": "private"}}}
    with pytest.raises(DouyinAvailabilityError):
        DouyinAdapter(FakeClient(payload)).get_post(aweme_id="private-1")


def test_search_maps_live_business_data_shape():
    aweme = load("video.json")["data"]["aweme_detail"]
    payload = {"data": {"business_data": [{"data": {"aweme_info": aweme}}]}}
    page = DouyinAdapter(FakeClient(payload)).search_posts("AI")
    assert page.items[0].post_id == "7350810998023949599"


def test_search_pagination_preserves_tikhub_search_state():
    payload = {
        "data": {
            "business_data": [],
            "business_config": {
                "has_more": 1,
                "next_page": {
                    "cursor": 20,
                    "keyword": "WorkBuddy 教程",
                    "search_id": "search-1",
                    "search_request_id": "request-1",
                },
            },
        },
    }
    client = FakeClient(payload)
    adapter = DouyinAdapter(client)
    first = adapter.search_posts("WorkBuddy 教程")
    adapter.search_posts("ignored", cursor=first.next_cursor)
    _, params = client.calls[1]
    assert params["cursor"] == 20
    assert params["keyword"] == "WorkBuddy 教程"
    assert params["search_id"] == "search-1"
    assert params["backtrace"] == "request-1"


def test_video_statistics_uses_aweme_ids_and_maps_play_count():
    payload = {"data": {"statistics_list": [{"aweme_id": "p1", "play_count": 585552, "digg_count": 10}]}}
    client = FakeClient(payload)
    stats = DouyinAdapter(client).get_video_statistics(["p1"])
    assert stats["p1"]["play_count"] == 585552
    assert client.calls[0][0] == "/api/v1/douyin/app/v3/fetch_video_statistics"
    assert client.calls[0][1] == {"aweme_ids": "p1"}


def test_detail_zero_play_count_is_missing_not_zero():
    payload = {"data": {"aweme_detail": {"aweme_id": "p1", "desc": "x", "statistics": {"play_count": 0}}}}
    post = DouyinAdapter(FakeClient(payload)).get_post(aweme_id="p1")
    assert post.views is None
    assert post.views_source is None


def test_search_accounts_maps_user_results():
    payload = {"data": {"user_list": [{"user_info": {"uid": "u1", "sec_uid": "sec-1", "nickname": "Creator", "follower_count": 1000}}], "cursor": 20, "has_more": 1}}
    page = DouyinAdapter(FakeClient(payload)).search_accounts("AI")
    assert page.items[0].account_id == "sec-1"
    assert page.items[0].followers == 1000
