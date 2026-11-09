"""Pit detection and measurement on calibrated AFM image data."""

from __future__ import annotations

from math import isfinite, pi, sqrt

import numpy as np
from skimage.filters import gaussian
from skimage.measure import regionprops
from skimage.morphology import footprint_rectangle, h_minima, local_minima

from afm_analysis.feature_geometry import (
    centered_extremum_height,
    local_reference,
    merge_seed_footprints,
)
from afm_analysis.feature_geometry import (
    projected_area as _projected_area,
)
from afm_analysis.models import EffectiveRequest, FeatureType, ImageData, PitResult
from afm_analysis.preprocessing import replace_local_extremes

MINIMUM_SEED_PROMINENCE_NM = 4.8
MAXIMUM_ASPECT_RATIO = 1.5


def _validate_image(image: ImageData) -> None:
    heights = image.heights_nm
    if heights.ndim != 2 or min(heights.shape) < 2:
        raise ValueError(
            "image heights must be a two-dimensional grid with at least two rows and columns"
        )
    if not np.isfinite(heights).all():
        raise ValueError("image heights must all be finite")
    pitches = (image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
    if not all(isfinite(pitch) and pitch > 0 for pitch in pitches):
        raise ValueError("pixel pitches must be positive finite numbers")


def analyze_pits(image: ImageData, request: EffectiveRequest) -> list[PitResult]:
    """Detect and measure pits using approved thresholds and boundary behavior."""
    _validate_image(image)
    if FeatureType.PIT not in request.feature_types or request.pit_thresholds is None:
        raise ValueError("effective request must include pit thresholds")

    filtered = replace_local_extremes(image.heights_nm)
    detection = gaussian(filtered, sigma=1, preserve_range=True)
    minima = local_minima(detection, connectivity=2)
    prominent_minima = h_minima(
        detection,
        MINIMUM_SEED_PROMINENCE_NM,
        footprint=footprint_rectangle((3, 3)), #ASK CODEX
    )
    seed_mask = minima & prominent_minima

    gradient_y, gradient_x = np.gradient( #ASK CODEX
        detection,
        image.pixel_pitch_y_nm,
        image.pixel_pitch_x_nm,
    )
    slope = np.hypot(gradient_x, gradient_y) #ASK CODEX
    candidates = merge_seed_footprints(
        seed_mask,
        slope,
        image.pixel_pitch_x_nm,
        image.pixel_pitch_y_nm,
    )

    thresholds = request.pit_thresholds
    global_median = float(np.median(filtered))
    measured: list[tuple[tuple[float, float], PitResult]] = []
    for region in regionprops(
        candidates,
        spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm),
    ):
        footprint = candidates == region.label
        reference = local_reference(footprint, filtered, global_median)
        area = _projected_area(footprint, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
        diameter = 2.0 * sqrt(area / pi)
        maximum_depth = reference - float(np.min(filtered[footprint]))
        if region.axis_minor_length <= 0:
            continue
        aspect_ratio = float(region.axis_major_length / region.axis_minor_length)
        if aspect_ratio >= MAXIMUM_ASPECT_RATIO:
            continue
        if maximum_depth < thresholds.depth_nm or diameter < thresholds.diameter_nm:
            continue

        measured.append(
            (
                (float(region.centroid[0]), float(region.centroid[1])),
                PitResult(
                    footprint=footprint,
                    area_nm2=area,
                    diameter_nm=diameter,
                    maximum_depth_nm=maximum_depth,
                    centered_height_nm=centered_extremum_height(
                        footprint, filtered, highest=False
                    ),
                    aspect_ratio=aspect_ratio,
                ),
            )
        )

    measured.sort(key=lambda item: item[0])
    return [result for _, result in measured]
