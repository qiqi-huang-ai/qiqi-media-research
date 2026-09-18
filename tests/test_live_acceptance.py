from tests.live.run_acceptance import acceptance_manifest


def test_dry_run_manifest_is_bounded_and_network_free():
    manifest = acceptance_manifest("all")
    assert manifest["network_calls_made"] == 0
    assert manifest["maximum_requests_total"] == 16
    assert set(manifest["platforms"]) == {"douyin", "xiaohongshu"}
