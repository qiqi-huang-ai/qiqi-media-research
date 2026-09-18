"""Transparent opportunity and evidence-confidence scoring."""

from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class OpportunityInputs:
    demand: float
    momentum: float
    supply: float
    relative_performance: float
    repeatability: float
    goal_fit: float


@dataclass(frozen=True, slots=True)
class OpportunityResult:
    score: float
    components: dict[str, float]


@dataclass(frozen=True, slots=True)
class Coverage:
    platforms: int
    posts: int
    comments: int
    missing_metric_ratio: float
    source_consistency: float = 1.0


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    label: str
    reasons: tuple[str, ...]


def score_opportunity(inputs: OpportunityInputs) -> OpportunityResult:
    values = {field.name: float(getattr(inputs, field.name)) for field in fields(inputs)}
    if any(value < 0 or value > 100 for value in values.values()):
        raise ValueError("opportunity dimensions must be between 0 and 100")
    components = {
        "demand": 0.24 * values["demand"],
        "momentum": 0.18 * values["momentum"],
        "low_supply": 0.18 * (100 - values["supply"]),
        "relative_performance": 0.16 * values["relative_performance"],
        "repeatability": 0.12 * values["repeatability"],
        "goal_fit": 0.12 * values["goal_fit"],
    }
    return OpportunityResult(round(sum(components.values()), 2), components)


def confidence_from_coverage(coverage: Coverage) -> ConfidenceResult:
    if coverage.platforms < 0 or coverage.posts < 0 or coverage.comments < 0:
        raise ValueError("coverage counts cannot be negative")
    if not 0 <= coverage.missing_metric_ratio <= 1 or not 0 <= coverage.source_consistency <= 1:
        raise ValueError("coverage ratios must be between 0 and 1")

    reasons = []
    if coverage.platforms < 2:
        reasons.append("only one platform covered")
    if coverage.posts < 10:
        reasons.append("fewer than 10 posts")
    if coverage.comments < 20:
        reasons.append("fewer than 20 comments")
    if coverage.missing_metric_ratio > 0.4:
        reasons.append("more than 40% of metrics are missing")
    if coverage.source_consistency < 0.7:
        reasons.append("source consistency is below 70%")

    high = (
        coverage.platforms >= 2
        and coverage.posts >= 30
        and coverage.comments >= 50
        and coverage.missing_metric_ratio <= 0.2
        and coverage.source_consistency >= 0.9
    )
    medium = (
        coverage.posts >= 10
        and coverage.comments >= 20
        and coverage.missing_metric_ratio <= 0.4
        and coverage.source_consistency >= 0.7
    )
    label = "high" if high else "medium" if medium else "low"
    if not reasons:
        reasons.append("coverage meets the configured threshold")
    return ConfidenceResult(label, tuple(reasons))
