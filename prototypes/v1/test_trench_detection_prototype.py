"""Focused computational checks for the standalone trench prototype."""

from pathlib import Path

import numpy as np
import pytest

from trench_detection_prototype import (
    detect_candidate_mask,
    load_afm_csv,
    measure_trenches,
)


DATASET = Path(__file__).resolve().parents[2] / "data" / "interview_line_space_image.csv"


def test_supplied_csv_loads_with_agreed_pixel_spacing() -> None:
    image = load_afm_csv(DATASET)

    assert image.heights_nm.shape == (500, 500)
    assert np.isfinite(image.heights_nm).all()
    assert image.spacing_i_nm == 1.0
    assert image.spacing_j_nm == 1.0
    assert 25.0 < np.median(image.heights_nm) < 35.0


def test_global_segmentation_is_rotation_symmetric() -> None:
    heights = np.full((100, 120), 30.0)
    for start in (15, 55, 95):
        heights[:, start : start + 8] = 0.0

    original_mask, _ = detect_candidate_mask(heights, gap_close_radius_pixels=0)
    original = measure_trenches(original_mask, heights, 1.0, 1.0)

    rotated_heights = np.rot90(heights)
    rotated_mask, _ = detect_candidate_mask(rotated_heights, gap_close_radius_pixels=0)
    rotated = measure_trenches(rotated_mask, rotated_heights, 1.0, 1.0)

    assert len(original) == len(rotated) == 3
    np.testing.assert_allclose(
        [feature.width_nm for feature in original],
        [feature.width_nm for feature in rotated],
        atol=0.1,
    )
    np.testing.assert_allclose(
        [feature.visible_length_nm for feature in original],
        [feature.visible_length_nm for feature in rotated],
        atol=0.1,
    )


def test_actual_dataset_produces_three_candidates() -> None:
    image = load_afm_csv(DATASET)
    mask, threshold_nm = detect_candidate_mask(image.heights_nm)
    trenches = measure_trenches(
        mask,
        image.heights_nm,
        image.spacing_i_nm,
        image.spacing_j_nm,
    )

    assert 10.0 < threshold_nm < 20.0
    assert len(trenches) == 3
    assert all(45.0 <= feature.width_nm <= 55.0 for feature in trenches)
    assert all(25.0 <= feature.depth_nm <= 35.0 for feature in trenches)
    assert all(500.0 <= feature.visible_length_nm <= 502.0 for feature in trenches)
    assert [feature.center_j for feature in trenches] == sorted(
        feature.center_j for feature in trenches
    )


def test_csv_matrix_shape_must_match_metadata(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.csv"
    malformed.write_text(
        "# ImageWidth,1e-8\n"
        "# ImageHeight,1e-8\n"
        "# ImageWidthPixel,3\n"
        "# ImageHeightPixel,3\n"
        "# ImageDataUnit,nm\n"
        "1,2\n"
        "3,4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="matrix shape does not match metadata"):
        load_afm_csv(malformed)
