from scripts.analyze import compute_post_metrics, count_comment_signals
from scripts.models import Comment, Post


def test_account_relative_performance_uses_median_views():
    posts = [
        Post(platform="douyin", post_id="1", source_url="u1", author_id="a", views=100, likes=10, comments=2, shares=1),
        Post(platform="douyin", post_id="2", source_url="u2", author_id="a", views=300, likes=30, comments=4, shares=2),
    ]
    result = compute_post_metrics(posts)
    assert result[0].relative_performance == 0.5
    assert result[1].relative_performance == 1.5
    assert result[0].relative_basis == "views"


def test_missing_views_does_not_create_engagement_rate():
    post = Post(platform="xiaohongshu", post_id="1", source_url="u", likes=20, comments=3, saves=8)
    metric = compute_post_metrics([post])[0]
    assert metric.engagement_rate is None


def test_missing_account_views_falls_back_to_likes():
    posts = [
        Post(platform="xiaohongshu", post_id="1", source_url="u1", author_id="a", likes=10),
        Post(platform="xiaohongshu", post_id="2", source_url="u2", author_id="a", likes=30),
    ]
    result = compute_post_metrics(posts)
    assert result[1].relative_performance == 1.5
    assert result[1].relative_basis == "likes"


def test_comment_signal_counts_are_explicit_keyword_matches():
    comments = [
        Comment(platform="douyin", comment_id="1", post_id="p", source_url="u", text="多少钱，求价格"),
        Comment(platform="douyin", comment_id="2", post_id="p", source_url="u", text="怎么买"),
    ]
    result = count_comment_signals(comments, {"price": ["价格", "多少钱"], "buy": ["怎么买"]})
    assert result == {"price": 1, "buy": 1}
