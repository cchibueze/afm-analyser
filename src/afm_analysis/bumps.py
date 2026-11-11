"""Bump detection and measurement on calibrated AFM image data."""

from __future__ import annotations

from math import isfinite, pi, sqrt

import numpy as np
from skimage.filters import gaussian
from skimage.measure import regionprops
from skimage.morphology import footprint_rectangle, h_maxima, local_maxima

from afm_analysis.feature_geometry import (
    centered_extremum_height,
    local_reference,
    merge_seed_footprints,
    projected_area,
)
from afm_analysis.models import BumpResult, EffectiveRequest, FeatureType, ImageData
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


def analyze_bumps(image: ImageData, request: EffectiveRequest) -> list[BumpResult]:
    """Detect and measure bumps using the approved thresholds and boundary behavior."""
    _validate_image(image)
    if FeatureType.BUMP not in request.feature_types or request.bump_thresholds is None:
        raise ValueError("effective request must include bump thresholds")

    filtered = replace_local_extremes(image.heights_nm)
    detection = gaussian(filtered, sigma=1, preserve_range=True)
    maxima = local_maxima(detection, connectivity=2)
    prominent_maxima = h_maxima(
        detection,
        MINIMUM_SEED_PROMINENCE_NM,
        footprint=footprint_rectangle((3, 3)),
    )
    seed_mask = maxima & prominent_maxima

    gradient_y, gradient_x = np.gradient(
        detection,
        image.pixel_pitch_y_nm,
        image.pixel_pitch_x_nm,
    )
    slope = np.hypot(gradient_x, gradient_y)
    candidates = merge_seed_footprints(
        seed_mask,
        slope,
        image.pixel_pitch_x_nm,
        image.pixel_pitch_y_nm,
    )

    thresholds = request.bump_thresholds
    global_median = float(np.median(filtered))
    measured: list[tuple[tuple[float, float], BumpResult]] = []
    for region in regionprops(
        candidates,
        spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm),
    ):
        footprint = candidates == region.label
        reference = local_reference(footprint, filtered, global_median)
        area = projected_area(footprint, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
        diameter = 2.0 * sqrt(area / pi)
        maximum_height = float(np.max(filtered[footprint])) - reference
        if region.axis_minor_length <= 0:
            continue
        aspect_ratio = float(region.axis_major_length / region.axis_minor_length)
        if aspect_ratio >= MAXIMUM_ASPECT_RATIO:
            continue
        if maximum_height < thresholds.height_nm or diameter < thresholds.diameter_nm:
            continue

        measured.append(
            (
                (float(region.centroid[0]), float(region.centroid[1])),
                BumpResult(
                    footprint=footprint,
                    area_nm2=area,
                    diameter_nm=diameter,
                    maximum_height_nm=maximum_height,
                    centered_height_nm=centered_extremum_height(
                        footprint, filtered, highest=True
                    ),
                    aspect_ratio=aspect_ratio,
                    centroid_x_pixel=float(region.centroid[1] / image.pixel_pitch_x_nm),
                    centroid_y_pixel=float(region.centroid[0] / image.pixel_pitch_y_nm),
                ),
            )
        )

    measured.sort(key=lambda item: item[0])
    return [result for _, result in measured]
