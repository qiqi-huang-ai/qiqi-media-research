import json

from scripts.collect import (
    CollectionPlan,
    estimate_requests,
    require_expansion_approval,
    write_manifest,
)


def test_request_estimate_counts_pages_and_details():
    plan = CollectionPlan(
        search_pages=2,
        accounts=3,
        posts_per_account_pages=2,
        post_details=8,
        comment_pages=4,
    )
    assert estimate_requests(plan) == 2 + 3 + 6 + 8 + 4


def test_over_twenty_requests_requires_notice():
    assert require_expansion_approval(20) is False
    assert require_expansion_approval(21) is True


def test_manifest_never_writes_credentials(tmp_path):
    target = write_manifest(
        tmp_path,
        platform="douyin",
        operation="search",
        parameters={"keyword": "AI", "TIKHUB_API_KEY": "secret", "authorization": "Bearer secret"},
        request_count=1,
        raw_paths=[tmp_path / "raw.json"],
        failures=[],
    )
    text = target.read_text()
    assert "secret" not in text
    assert json.loads(text)["parameters"] == {"keyword": "AI"}


def test_negative_plan_values_are_rejected():
    try:
        estimate_requests(CollectionPlan(search_pages=-1))
    except ValueError:
        pass
    else:
        raise AssertionError("negative request counts must fail")
