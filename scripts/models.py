"""Normalized, platform-neutral records used by the research pipeline."""

from dataclasses import dataclass


@dataclass(slots=True)
class Account:
    platform: str
    account_id: str
    source_url: str
    name: str | None = None
    bio: str | None = None
    followers: int | None = None
    following: int | None = None
    posts: int | None = None
    likes_received: int | None = None
    collected_at: str | None = None
    raw_path: str | None = None


@dataclass(slots=True)
class Post:
    platform: str
    post_id: str
    source_url: str
    author_id: str | None = None
    author_name: str | None = None
    text: str | None = None
    published_at: str | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    followers: int | None = None
    duration_sec: float | None = None
    collected_at: str | None = None
    raw_path: str | None = None


@dataclass(slots=True)
class Comment:
    platform: str
    comment_id: str
    post_id: str
    source_url: str
    author_id: str | None = None
    author_name: str | None = None
    text: str | None = None
    published_at: str | None = None
    likes: int | None = None
    reply_count: int | None = None
    parent_comment_id: str | None = None
    collected_at: str | None = None
    raw_path: str | None = None


@dataclass(slots=True)
class TrendItem:
    platform: str
    trend_id: str
    title: str
    source_url: str
    rank: int | None = None
    score: float | None = None
    category: str | None = None
    collected_at: str | None = None
    raw_path: str | None = None


@dataclass(slots=True)
class EvidenceRecord:
    evidence_id: str
    platform: str
    entity_type: str
    entity_id: str
    source_url: str
    source_field: str
    value: str | int | float | bool | None
    collected_at: str | None = None
    raw_path: str | None = None
