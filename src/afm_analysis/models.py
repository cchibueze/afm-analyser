"""Data models used by AFM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _validate_centroid(
    footprint: NDArray[np.bool_], centroid_x_pixel: float, centroid_y_pixel: float
) -> None:
    """Require finite centroid coordinates matching the footprint's pixel mean."""
    if footprint.ndim != 2:
        raise ValueError("feature footprint must be a two-dimensional array")
    coordinates = np.argwhere(footprint)
    if not len(coordinates):
        raise ValueError("feature footprint must not be empty")
    if not np.isfinite((centroid_x_pixel, centroid_y_pixel)).all():
        raise ValueError("feature centroid coordinates must be finite")
    expected_y, expected_x = coordinates.mean(axis=0)
    if not np.isclose(centroid_x_pixel, expected_x, rtol=0.0, atol=1e-9) or not np.isclose(
        centroid_y_pixel, expected_y, rtol=0.0, atol=1e-9
    ):
        raise ValueError("feature centroid must match the mean pixel indices of its footprint")


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


@dataclass(frozen=True)
class ImageData:
    """AFM height grid and calibrated image geometry, with distances in nm.

    ``length_nm`` is the physical extent along the matrix row (Y) axis;
    ``heights_nm`` contains the measured surface height at each grid point.
    """

    heights_nm: FloatArray
    width_nm: float
    length_nm: float
    width_pixels: int
    length_pixels: int
    pixel_pitch_x_nm: float
    pixel_pitch_y_nm: float


@dataclass(frozen=True)
class TrenchResult:
    """Measured trench and its boolean pixel footprint."""

    footprint: NDArray[np.bool_]
    length_nm: float
    width_nm: float
    depth_nm: float
    centroid_x_pixel: float
    centroid_y_pixel: float

    def __post_init__(self) -> None:
        _validate_centroid(self.footprint, self.centroid_x_pixel, self.centroid_y_pixel)


@dataclass(frozen=True)
class PitResult:
    """Measured pit and its boolean pixel footprint."""

    footprint: NDArray[np.bool_]
    area_nm2: float
    diameter_nm: float
    maximum_depth_nm: float
    centered_height_nm: float
    aspect_ratio: float
    centroid_x_pixel: float
    centroid_y_pixel: float

    def __post_init__(self) -> None:
        _validate_centroid(self.footprint, self.centroid_x_pixel, self.centroid_y_pixel)


@dataclass(frozen=True)
class BumpResult:
    """Measured bump and its boolean pixel footprint."""

    footprint: NDArray[np.bool_]
    area_nm2: float
    diameter_nm: float
    maximum_height_nm: float
    centered_height_nm: float
    aspect_ratio: float
    centroid_x_pixel: float
    centroid_y_pixel: float

    def __post_init__(self) -> None:
        _validate_centroid(self.footprint, self.centroid_x_pixel, self.centroid_y_pixel)


@dataclass(frozen=True)
class SelectedCandidates:
    """Selected results separated into feature-specific, centroid-ordered lists."""

    trenches: list[TrenchResult]
    pits: list[PitResult]
    bumps: list[BumpResult]
