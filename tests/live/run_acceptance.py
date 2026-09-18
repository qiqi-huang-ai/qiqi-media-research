"""Opt-in live acceptance planner. Dry-run performs zero network calls."""

import argparse
import json
import os


MAX_SEARCH_PAGES = 1
MAX_ACCOUNT_POST_PAGES = 2
MAX_COMMENT_PAGES = 1
MAX_POST_DETAILS = 3


OPERATIONS = {
    "douyin": [
        "search",
        "account",
        "account_posts",
        "post_detail",
        "comments",
        "pagination_check",
        "normalization",
        "analysis",
        "report",
    ],
    "xiaohongshu": [
        "search",
        "account",
        "account_posts",
        "post_detail",
        "comments",
        "pagination_check",
        "normalization",
        "analysis",
        "report",
    ],
}


def request_cap_per_platform() -> int:
    # The pagination check is performed within the two capped account-post pages.
    return MAX_SEARCH_PAGES + 1 + MAX_ACCOUNT_POST_PAGES + MAX_POST_DETAILS + MAX_COMMENT_PAGES


def acceptance_manifest(platform: str) -> dict[str, object]:
    platforms = list(OPERATIONS) if platform == "all" else [platform]
    return {
        "dry_run": True,
        "network_calls_made": 0,
        "platforms": {
            name: {
                "operations": OPERATIONS[name],
                "maximum_requests": request_cap_per_platform(),
                "caps": {
                    "search_pages": MAX_SEARCH_PAGES,
                    "account_post_pages": MAX_ACCOUNT_POST_PAGES,
                    "comment_pages": MAX_COMMENT_PAGES,
                    "post_details": MAX_POST_DETAILS,
                },
            }
            for name in platforms
        },
        "maximum_requests_total": request_cap_per_platform() * len(platforms),
        "billing_notice": "TikHub pricing may change; Douyin Search is separately billed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("douyin", "xiaohongshu", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--douyin-keyword")
    parser.add_argument("--xiaohongshu-keyword")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(acceptance_manifest(args.platform), ensure_ascii=False, indent=2))
        return 0
    if not os.environ.get("TIKHUB_API_KEY"):
        parser.error("TIKHUB_API_KEY is missing")
    parser.error("live execution requires the approved request cap to be implemented and reviewed")


if __name__ == "__main__":
    raise SystemExit(main())
