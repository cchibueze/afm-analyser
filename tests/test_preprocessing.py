"""Tests for feature-specific height preprocessing."""

import numpy as np
import pytest

from afm_analysis.preprocessing import replace_local_extremes


def test_replaces_high_and_low_extremes_with_leave_one_out_local_mean() -> None:
    heights = np.full((31, 31), 5.0)
    heights[5, 5] = 2005.1
    heights[25, 25] = -1995.1

    filtered = replace_local_extremes(heights)

    assert filtered[5, 5] == pytest.approx(5.0)
    assert filtered[25, 25] == pytest.approx(5.0)
    assert filtered[0, 0] == pytest.approx(5.0)


def test_does_not_replace_values_at_or_within_cutoff() -> None:
    heights = np.full((15, 15), 0.0)
    heights[7, 7] = 1000.0

    filtered = replace_local_extremes(heights)

    assert filtered[7, 7] == 1000.0


def test_edge_window_uses_available_neighbors_and_excludes_target() -> None:
    heights = np.full((5, 5), 12.0)
    heights[0, 0] = 2012.5

    filtered = replace_local_extremes(heights)

    assert filtered[0, 0] == pytest.approx(12.0)


@pytest.mark.parametrize("heights", [np.zeros(4), np.full((3, 3), np.nan)])
def test_rejects_non_2d_or_non_finite_heights(heights: np.ndarray) -> None:
    with pytest.raises(ValueError):
        replace_local_extremes(heights)


