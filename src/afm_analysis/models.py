"""Data models for validated operator analysis requests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FeatureType(StrEnum):
    """Feature types supported by the initial analysis scope."""

    TRENCH = "trench"
    BUMP = "bump"
    PIT = "pit"


@dataclass(frozen=True)
class TrenchThresholds:
    """Trench minimum dimensions and depth, expressed in nanometers."""

    depth_nm: float
    width_nm: float
    length_nm: float


@dataclass(frozen=True)
class BumpThresholds:
    """Minimum bump height and diameter, expressed in nanometers."""

    height_nm: float
    diameter_nm: float


@dataclass(frozen=True)
class PitThresholds:
    """Minimum pit depth and diameter, expressed in nanometers."""

    depth_nm: float
    diameter_nm: float


@dataclass(frozen=True)
class EffectiveRequest:
    """Validated feature selection and thresholds with defaults applied."""

    feature_types: frozenset[FeatureType]
    trench_thresholds: TrenchThresholds | None = None
    bump_thresholds: BumpThresholds | None = None
    pit_thresholds: PitThresholds | None = None
