"""Image preprocessing shared by bump and pit detection."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

LOCAL_MEAN_WINDOW_PIXELS = 11
LOCAL_EXTREME_CUTOFF_NM = 1000.0


def replace_local_extremes(heights_nm: np.ndarray) -> np.ndarray:
    """Replace points over 1000 nm from their leave-one-out local mean.

    The local mean uses the available pixels in a centered 11x11 window,
    excluding the point being evaluated. At image edges, the window is clipped
    to the image. All replacement values are computed from the input image so
    the result does not depend on the order in which pixels are visited.
    """
    if heights_nm.ndim != 2:
        raise ValueError("heights must be a two-dimensional grid")
    if not np.isfinite(heights_nm).all():
        raise ValueError("heights must all be finite")

    values = np.asarray(heights_nm, dtype=np.float64)
    window_size = LOCAL_MEAN_WINDOW_PIXELS
    window_area = window_size * window_size
    local_sum = uniform_filter(
        values,
        size=window_size,
        mode="constant",
        cval=0.0,
    ) * window_area
    local_count = uniform_filter(
        np.ones(values.shape, dtype=np.float64),
        size=window_size,
        mode="constant",
        cval=0.0,
    ) * window_area

    neighbor_count = local_count - 1.0
    local_mean = (local_sum - values) / neighbor_count
    extreme = np.abs(values - local_mean) > LOCAL_EXTREME_CUTOFF_NM

    filtered = values.copy()
    filtered[extreme] = local_mean[extreme]
    return filtered
