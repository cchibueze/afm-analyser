import pytest

from afm_analysis.models import BumpThresholds, FeatureType, PitThresholds
from afm_analysis.requests import Request, validate_request


def test_defaults_to_trenches_with_approved_thresholds() -> None:
    effective = validate_request(Request())

    assert effective.feature_types == frozenset({FeatureType.TRENCH})
    assert effective.trench_thresholds is not None
    assert effective.trench_thresholds.depth_nm == 5.0
    assert effective.trench_thresholds.width_nm == 3.0
    assert effective.trench_thresholds.length_nm == 6.0
    assert effective.bump_thresholds is None
    assert effective.pit_thresholds is None


def test_round_feature_defaults_are_applied_only_when_requested() -> None:
    effective = validate_request(Request(feature_types=["bump", "pit"]))

    assert effective.bump_thresholds is not None
    assert isinstance(effective.bump_thresholds, BumpThresholds)
    assert effective.bump_thresholds.height_nm == 4.0
    assert effective.bump_thresholds.diameter_nm == 4.0
    assert effective.pit_thresholds is not None
    assert isinstance(effective.pit_thresholds, PitThresholds)
    assert effective.pit_thresholds.depth_nm == 4.0
    assert effective.pit_thresholds.diameter_nm == 4.0
    assert effective.trench_thresholds is None


def test_valid_threshold_overrides_are_preserved() -> None:
    effective = validate_request(
        Request(trench_depth_nm=7.0, trench_width_nm=4.0, trench_length_nm=6.0)
    )

    assert effective.trench_thresholds is not None
    assert effective.trench_thresholds.depth_nm == 7.0
    assert effective.trench_thresholds.width_nm == 4.0
    assert effective.trench_thresholds.length_nm == 6.0


@pytest.mark.parametrize("feature_type", ["ridge", "", "TRENCH"])
def test_unsupported_feature_type_is_rejected(feature_type: str) -> None:
    with pytest.raises(ValueError, match="Unsupported feature type"):
        validate_request(Request(feature_types=[feature_type]))


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_non_positive_or_non_finite_threshold_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        validate_request(Request(trench_depth_nm=value))


def test_empty_feature_selection_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        validate_request(Request(feature_types=[]))


def test_trench_length_must_be_at_least_one_and_a_half_times_width() -> None:
    with pytest.raises(ValueError, match="at least 1.5 times"):
        validate_request(Request(trench_width_nm=4.0, trench_length_nm=5.9))
