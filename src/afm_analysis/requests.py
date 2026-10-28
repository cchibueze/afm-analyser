"""Validation and defaults for programmatic operator requests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from afm_analysis.models import (
    BumpThresholds,
    EffectiveRequest,
    FeatureType,
    PitThresholds,
    TrenchThresholds,
)

MIN_TRENCH_LENGTH_TO_WIDTH_RATIO = 1.5


@dataclass(frozen=True)
class Request:
    """Optional operator choices before documented defaults are applied."""

    feature_types: Iterable[FeatureType | str] | None = None
    trench_depth_nm: float | None = None
    trench_width_nm: float | None = None
    trench_length_nm: float | None = None
    bump_height_nm: float | None = None
    bump_diameter_nm: float | None = None
    pit_depth_nm: float | None = None
    pit_diameter_nm: float | None = None


def _positive_finite(value: float, name: str) -> float:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def _feature_types(values: Iterable[FeatureType | str] | None) -> frozenset[FeatureType]:
    if values is None:
        return frozenset({FeatureType.TRENCH})
    try:
        parsed = frozenset(FeatureType(value) for value in values)
    except ValueError as error:
        raise ValueError(f"Unsupported feature type: {error}") from error
    if not parsed:
        raise ValueError("feature_types must not be empty when specified")
    return parsed


def validate_request(request: Request) -> EffectiveRequest:
    """Validate a request and apply nanometer threshold defaults."""
    features = _feature_types(request.feature_types)

    trench = None
    if FeatureType.TRENCH in features:
        trench = TrenchThresholds(
            depth_nm=_positive_finite(
                5.0 if request.trench_depth_nm is None else request.trench_depth_nm,
                "trench_depth_nm",
            ),
            width_nm=_positive_finite(
                3.0 if request.trench_width_nm is None else request.trench_width_nm,
                "trench_width_nm",
            ),
            length_nm=_positive_finite(
                6.0 if request.trench_length_nm is None else request.trench_length_nm,
                "trench_length_nm",
            ),
        )
        if trench.length_nm / trench.width_nm < MIN_TRENCH_LENGTH_TO_WIDTH_RATIO:
            raise ValueError("trench_length_nm must be at least 1.5 times trench_width_nm")

    bump = None
    if FeatureType.BUMP in features:
        bump = BumpThresholds(
            height_nm=_positive_finite(
                4.0 if request.bump_height_nm is None else request.bump_height_nm,
                "bump_height_nm",
            ),
            diameter_nm=_positive_finite(
                4.0 if request.bump_diameter_nm is None else request.bump_diameter_nm,
                "bump_diameter_nm",
            ),
        )

    pit = None
    if FeatureType.PIT in features:
        pit = PitThresholds(
            depth_nm=_positive_finite(
                4.0 if request.pit_depth_nm is None else request.pit_depth_nm,
                "pit_depth_nm",
            ),
            diameter_nm=_positive_finite(
                4.0 if request.pit_diameter_nm is None else request.pit_diameter_nm,
                "pit_diameter_nm",
            ),
        )

    return EffectiveRequest(
        feature_types=features,
        trench_thresholds=trench,
        bump_thresholds=bump,
        pit_thresholds=pit,
    )
