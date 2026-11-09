"""Shared geometric operations for bump and pit candidates."""

from __future__ import annotations

from math import ceil, cos, pi, sin, sqrt

import numpy as np
from skimage.draw import polygon
from skimage.measure import label, regionprops
from skimage.morphology import dilation, footprint_rectangle

LOCAL_REFERENCE_SIZE_PIXELS = 11
SLOPE_THRESHOLD_GRADE = 0.2


def grow_seed(seed: np.ndarray, slope: np.ndarray, pitch_x: float, pitch_y: float) -> np.ndarray:
    """Grow radial branches to the first low-slope location after the steep flank."""
    rows, columns = seed.shape
    seed_pixels = np.argwhere(seed)
    center_row, center_column = seed_pixels.mean(axis=0)
    step_size = min(pitch_x, pitch_y) / 2.0
    farthest_edge = max(
        sqrt((row * pitch_y) ** 2 + (column * pitch_x) ** 2)
        for row in (center_row, rows - 1 - center_row)
        for column in (center_column, columns - 1 - center_column)
    )
    steps = ceil(farthest_edge / step_size)
    boundary_rows = [float(row) for row, _ in seed_pixels]
    boundary_columns = [float(column) for _, column in seed_pixels]

    for angle in np.linspace(0.0, 2.0 * pi, num=360, endpoint=False):
        steep_seen = False
        last_row = int(round(center_row))
        last_column = int(round(center_column))
        for step in range(1, steps + 1):
            distance = step * step_size
            row = int(round(center_row + sin(angle) * distance / pitch_y))
            column = int(round(center_column + cos(angle) * distance / pitch_x))
            if not (0 <= row < rows and 0 <= column < columns):
                break
            is_steep = bool(slope[row, column] >= SLOPE_THRESHOLD_GRADE)
            if steep_seen and not is_steep:
                break
            steep_seen |= is_steep
            last_row, last_column = row, column
        boundary_rows.append(float(last_row))
        boundary_columns.append(float(last_column))

    grown_rows, grown_columns = polygon(boundary_rows, boundary_columns, shape=seed.shape)
    footprint = np.zeros(seed.shape, dtype=bool)
    footprint[grown_rows, grown_columns] = True
    footprint |= seed
    return footprint


def merge_seed_footprints(
    seed_mask: np.ndarray, slope: np.ndarray, pitch_x: float, pitch_y: float
) -> np.ndarray:
    """Grow extrema independently, then merge footprints that touch in 8-connectivity."""
    seed_labels = label(seed_mask, connectivity=2)
    grown = np.zeros(seed_mask.shape, dtype=bool)
    for seed_region in regionprops(seed_labels):
        seed = seed_labels == seed_region.label
        grown |= grow_seed(seed, slope, pitch_x, pitch_y)
    return label(grown, connectivity=2)


def local_reference(candidate: np.ndarray, filtered: np.ndarray, global_median: float) -> float:
    """Average the qualifying 11×11 shell, falling back to the image median."""
    shell = dilation(
        candidate,
        footprint=footprint_rectangle((LOCAL_REFERENCE_SIZE_PIXELS, LOCAL_REFERENCE_SIZE_PIXELS)),
        mode="ignore",
    ) & ~candidate
    shell &= filtered >= global_median
    if shell.any():
        return float(np.mean(filtered[shell]))
    return global_median


def projected_area(footprint: np.ndarray, pitch_x: float, pitch_y: float) -> float:
    """Sum calibrated pixel-cell areas, clipping cells at each image edge."""
    row_areas = np.full(footprint.shape[0], pitch_y, dtype=np.float64)
    column_areas = np.full(footprint.shape[1], pitch_x, dtype=np.float64)
    row_areas[[0, -1]] *= 0.5
    column_areas[[0, -1]] *= 0.5
    return float(np.sum(footprint * np.outer(row_areas, column_areas)))


def centered_extremum_height(
    footprint: np.ndarray, filtered: np.ndarray, *, highest: bool
) -> float:
    """Average filtered heights in a clipped 3×3 window around the footprint extremum."""
    extremum = -np.inf if highest else np.inf
    footprint_heights = np.where(footprint, filtered, extremum)
    index = np.argmax(footprint_heights) if highest else np.argmin(footprint_heights)
    row, column = np.unravel_index(int(index), footprint.shape)
    row_start, row_stop = max(0, row - 1), min(filtered.shape[0], row + 2)
    column_start, column_stop = max(0, column - 1), min(filtered.shape[1], column + 2)
    return float(np.mean(filtered[row_start:row_stop, column_start:column_stop]))



