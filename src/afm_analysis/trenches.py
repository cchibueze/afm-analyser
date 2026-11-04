"""Trench detection and measurement on calibrated AFM image data."""

from __future__ import annotations

from math import isfinite, sqrt

import numpy as np
from skimage.filters import gaussian, threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import closing, dilation, footprint_rectangle

from afm_analysis.models import EffectiveRequest, FeatureType, ImageData, TrenchResult

RECTANGLE_MOMENT_CORRECTION = sqrt(3.0) / 2.0
LOCAL_REFERENCE_SIZE_PIXELS = 11
MINIMUM_ASPECT_RATIO = 1.5


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


def _filter_outliers(heights: np.ndarray) -> np.ndarray:
    mean = float(np.mean(heights))
    standard_deviation = float(np.std(heights))
    if standard_deviation == 0.0:
        return heights.copy()
    outliers = np.abs((heights - mean) / standard_deviation) > 3.0
    filtered = heights.copy()
    filtered[outliers] = mean
    return filtered


def _local_reference(
    candidate: np.ndarray, filtered: np.ndarray, global_median: float
) -> float:
    shell = dilation(
        candidate,
        footprint=footprint_rectangle((LOCAL_REFERENCE_SIZE_PIXELS, LOCAL_REFERENCE_SIZE_PIXELS)),
        mode="ignore",
    ) & ~candidate
    shell &= filtered >= global_median
    if shell.any():
        return float(np.mean(filtered[shell]))
    return global_median


def analyze_trenches(image: ImageData, request: EffectiveRequest) -> list[TrenchResult]:
    """Detect and measure trenches using the approved definitions.

    Otsu thresholding and one-pixel square closing generate candidate regions
    from the sigma-1 detection image. The requested depth threshold then forms
    each measured footprint from the filtered, unsmoothed image.
    """
    _validate_image(image)
    if FeatureType.TRENCH not in request.feature_types or request.trench_thresholds is None:
        raise ValueError("effective request must include trench thresholds")

    filtered = _filter_outliers(image.heights_nm)
    detection = gaussian(filtered, sigma=1, preserve_range=True)
    candidate_mask = detection < float(threshold_otsu(detection))
    candidate_mask = closing(
        candidate_mask,
        footprint=footprint_rectangle((3, 3)),
        mode="ignore",
    )
    candidates = label(candidate_mask, connectivity=2)

    thresholds = request.trench_thresholds
    global_median = float(np.median(filtered))
    measured: list[tuple[tuple[float, float], TrenchResult]] = []
    for candidate_region in regionprops(candidates):
        candidate = candidates == candidate_region.label
        reference = _local_reference(candidate, filtered, global_median)
        final_mask = candidate & (reference - filtered >= thresholds.depth_nm)
        final_labels = label(final_mask, connectivity=2)

        for region in regionprops(
            final_labels,
            spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm),
        ):
            if region.axis_minor_length <= 0:
                continue
            aspect_ratio = float(region.axis_major_length / region.axis_minor_length)
            if aspect_ratio <= MINIMUM_ASPECT_RATIO:
                continue

            length = float(region.axis_major_length * RECTANGLE_MOMENT_CORRECTION)
            width = float(region.axis_minor_length * RECTANGLE_MOMENT_CORRECTION)
            region_mask = final_labels == region.label
            depth = reference - float(np.mean(filtered[region_mask]))
            if (
                length < thresholds.length_nm
                or width < thresholds.width_nm
                or depth < thresholds.depth_nm
            ):
                continue

            measured.append(
                (
                    (float(region.centroid[0]), float(region.centroid[1])),
                    TrenchResult(
                        footprint=region_mask,
                        length_nm=length,
                        width_nm=width,
                        depth_nm=depth,
                    ),
                )
            )

    measured.sort(key=lambda item: item[0])
    return [result for _, result in measured]
