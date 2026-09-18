import pytest

from scripts.score import Coverage, OpportunityInputs, confidence_from_coverage, score_opportunity


def test_opportunity_score_is_bounded_and_supply_is_inverted():
    low_supply = score_opportunity(OpportunityInputs(80, 70, 20, 75, 60, 90))
    high_supply = score_opportunity(OpportunityInputs(80, 70, 90, 75, 60, 90))
    assert 0 <= low_supply.score <= 100
    assert low_supply.score > high_supply.score


def test_invalid_dimension_is_rejected():
    with pytest.raises(ValueError):
        score_opportunity(OpportunityInputs(101, 50, 50, 50, 50, 50))


def test_sparse_coverage_is_low_confidence():
    result = confidence_from_coverage(Coverage(platforms=1, posts=4, comments=0, missing_metric_ratio=0.6))
    assert result.label == "low"


def test_confidence_does_not_change_opportunity_score():
    inputs = OpportunityInputs(80, 70, 20, 75, 60, 90)
    assert score_opportunity(inputs).score == score_opportunity(inputs).score
