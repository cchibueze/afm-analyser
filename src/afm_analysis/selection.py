"""Group and prioritize measured feature candidates."""

from __future__ import annotations

from math import pi, sqrt

import numpy as np
from skimage.measure import label, regionprops
from skimage.morphology import dilation, footprint_rectangle

from afm_analysis.feature_geometry import centered_extremum_height, local_reference, projected_area
from afm_analysis.models import (
    BumpResult,
    EffectiveRequest,
    FeatureType,
    ImageData,
    PitResult,
    SelectedCandidates,
    TrenchResult,
)
from afm_analysis.preprocessing import replace_local_extremes
from afm_analysis.trenches import (
    LOCAL_REFERENCE_SIZE_PIXELS as TRENCH_LOCAL_REFERENCE_SIZE_PIXELS,
)
from afm_analysis.trenches import (
    RECTANGLE_MOMENT_CORRECTION,
    _filter_outliers,
)

_PRIORITY = {FeatureType.TRENCH: 0, FeatureType.PIT: 1, FeatureType.BUMP: 2}
_SELECTION_OVERLAP = 0.80


def select_candidates(
    image: ImageData,
    request: EffectiveRequest,
    trenches: list[TrenchResult],
    pits: list[PitResult],
    bumps: list[BumpResult],
) -> SelectedCandidates:
    """Merge same-type footprints, remeasure, then apply cross-type priority.

    Mixed-type suppression requires intersection / union area >= 0.80. Pixel
    areas use calibrated pitches and half cells at the image edges.
    """
    grouped: dict[FeatureType, list[TrenchResult | PitResult | BumpResult]] = {
        FeatureType.TRENCH: _remeasure_trenches(image, request, trenches),
        FeatureType.PIT: _remeasure_pits(image, request, pits),
        FeatureType.BUMP: _remeasure_bumps(image, request, bumps),
    }
    retained: dict[FeatureType, list[TrenchResult | PitResult | BumpResult]] = {
        FeatureType.TRENCH: [],
        FeatureType.PIT: [],
        FeatureType.BUMP: [],
    }
    for feature in (FeatureType.TRENCH, FeatureType.PIT, FeatureType.BUMP):
        for candidate in grouped[feature]:
            if any(
                _overlap_ratio(image, candidate.footprint, higher.footprint) >= _SELECTION_OVERLAP
                for higher_feature in (FeatureType.TRENCH, FeatureType.PIT)
                if _PRIORITY[higher_feature] < _PRIORITY[feature]
                for higher in retained[higher_feature]
            ):
                continue
            retained[feature].append(candidate)
    return SelectedCandidates(
        trenches=sorted(retained[FeatureType.TRENCH], key=lambda item: _centroid(item.footprint)),
        pits=sorted(retained[FeatureType.PIT], key=lambda item: _centroid(item.footprint)),
        bumps=sorted(retained[FeatureType.BUMP], key=lambda item: _centroid(item.footprint)),
    )


def _groups(
    candidates: list[TrenchResult] | list[PitResult] | list[BumpResult], shape: tuple[int, int]
) -> list[np.ndarray]:
    if not candidates:
        return []
    combined = np.zeros(shape, dtype=bool)
    for candidate in candidates:
        if candidate.footprint.shape != shape:
            raise ValueError("candidate footprint shape must match image heights")
        combined |= candidate.footprint
    labels = label(combined, connectivity=2)
    masks = [labels == region.label for region in regionprops(labels)]
    return sorted(masks, key=_centroid)


def _remeasure_trenches(
    image: ImageData, request: EffectiveRequest, candidates: list[TrenchResult]
) -> list[TrenchResult]:
    thresholds = request.trench_thresholds
    if not candidates or thresholds is None:
        return []
    filtered = _filter_outliers(image.heights_nm)
    median = float(np.median(filtered))

    shell_footprint = footprint_rectangle((TRENCH_LOCAL_REFERENCE_SIZE_PIXELS,) * 2)
    output = []
    for mask in _groups(candidates, image.heights_nm.shape):
        shell = dilation(mask, footprint=shell_footprint, mode="ignore") & ~mask
        shell &= filtered >= median
        reference = float(np.mean(filtered[shell])) if shell.any() else median
        regions = label(mask, connectivity=2)
        for region in regionprops(
            regions, spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm)
        ):
            footprint = regions == region.label
            if (
                region.axis_minor_length <= 0
                or region.axis_major_length / region.axis_minor_length <= 1.5
            ):
                continue
            length = float(region.axis_major_length * RECTANGLE_MOMENT_CORRECTION)
            width = float(region.axis_minor_length * RECTANGLE_MOMENT_CORRECTION)
            depth = reference - float(np.mean(filtered[footprint]))
            if (
                length >= thresholds.length_nm
                and width >= thresholds.width_nm
                and depth >= thresholds.depth_nm
            ):
                centroid_y, centroid_x = _centroid(footprint)
                output.append(
                    TrenchResult(
                        footprint,
                        length,
                        width,
                        depth,
                        centroid_x_pixel=centroid_x,
                        centroid_y_pixel=centroid_y,
                    )
                )
    return output


def _remeasure_pits(
    image: ImageData, request: EffectiveRequest, candidates: list[PitResult]
) -> list[PitResult]:
    thresholds = request.pit_thresholds
    if not candidates or thresholds is None:
        return []
    filtered = replace_local_extremes(image.heights_nm)
    output = []
    for footprint in _groups(candidates, image.heights_nm.shape):
        region = regionprops(
            footprint.astype(np.uint8), spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm)
        )[0]
        reference = local_reference(footprint, filtered, float(np.median(filtered)))
        area = projected_area(footprint, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
        diameter = 2.0 * sqrt(area / pi)
        depth = reference - float(np.min(filtered[footprint]))
        aspect = (
            float(region.axis_major_length / region.axis_minor_length)
            if region.axis_minor_length
            else float("inf")
        )
        if depth >= thresholds.depth_nm and diameter >= thresholds.diameter_nm and aspect < 1.5:
            output.append(
                PitResult(
                    footprint,
                    area,
                    diameter,
                    depth,
                    centered_extremum_height(footprint, filtered, highest=False),
                    aspect,
                    centroid_x_pixel=_centroid(footprint)[1],
                    centroid_y_pixel=_centroid(footprint)[0],
                )
            )
    return output


def _remeasure_bumps(
    image: ImageData, request: EffectiveRequest, candidates: list[BumpResult]
) -> list[BumpResult]:
    thresholds = request.bump_thresholds
    if not candidates or thresholds is None:
        return []
    filtered = replace_local_extremes(image.heights_nm)
    output = []
    for footprint in _groups(candidates, image.heights_nm.shape):
        region = regionprops(
            footprint.astype(np.uint8), spacing=(image.pixel_pitch_y_nm, image.pixel_pitch_x_nm)
        )[0]
        reference = local_reference(footprint, filtered, float(np.median(filtered)))
        area = projected_area(footprint, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
        diameter = 2.0 * sqrt(area / pi)
        height = float(np.max(filtered[footprint])) - reference
        aspect = (
            float(region.axis_major_length / region.axis_minor_length)
            if region.axis_minor_length
            else float("inf")
        )
        if height >= thresholds.height_nm and diameter >= thresholds.diameter_nm and aspect < 1.5:
            output.append(
                BumpResult(
                    footprint,
                    area,
                    diameter,
                    height,
                    centered_extremum_height(footprint, filtered, highest=True),
                    aspect,
                    centroid_x_pixel=_centroid(footprint)[1],
                    centroid_y_pixel=_centroid(footprint)[0],
                )
            )
    return output


def _centroid(footprint: np.ndarray) -> tuple[float, float]:
    return tuple(float(value) for value in np.argwhere(footprint).mean(axis=0))


def _overlap_ratio(image: ImageData, first: np.ndarray, second: np.ndarray) -> float:
    intersection = first & second
    if not intersection.any():
        return 0.0
    overlap = projected_area(intersection, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
    union = projected_area(first | second, image.pixel_pitch_x_nm, image.pixel_pitch_y_nm)
    return overlap / union
