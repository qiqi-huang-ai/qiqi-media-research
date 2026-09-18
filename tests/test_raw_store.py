import json

from scripts.models import Post
from scripts.raw_store import RawStore, write_jsonl


def test_post_keeps_missing_metrics_as_none():
    post = Post(platform="xiaohongshu", post_id="n1", source_url="https://example/n1")
    assert post.views is None
    assert post.saves is None


def test_raw_store_never_overwrites(tmp_path):
    store = RawStore(tmp_path)
    first = store.save("douyin", "video-detail", {"data": {"id": 1}})
    second = store.save("douyin", "video-detail", {"data": {"id": 2}})
    assert first != second
    assert json.loads(first.read_text())["data"]["id"] == 1


def test_jsonl_serializes_dataclass(tmp_path):
    target = tmp_path / "posts.jsonl"
    write_jsonl(
        target,
        [Post(platform="douyin", post_id="a1", source_url="https://example/a1")],
    )
    assert json.loads(target.read_text().strip())["post_id"] == "a1"
