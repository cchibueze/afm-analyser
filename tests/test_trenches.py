"""Production trench detection and measurement tests."""

from pathlib import Path

import numpy as np
import pytest

from afm_analysis.csv_reader import read_csv
from afm_analysis.models import EffectiveRequest, FeatureType, ImageData, TrenchThresholds
from afm_analysis.trenches import _filter_outliers, analyze_trenches


def _request(depth: float = 5.0) -> EffectiveRequest:
    return EffectiveRequest(
        feature_types=frozenset({FeatureType.TRENCH}),
        trench_thresholds=TrenchThresholds(depth, 3.0, 6.0),
    )


def _image(heights: np.ndarray, pitch_x: float = 1.0, pitch_y: float = 1.0) -> ImageData:
    rows, columns = heights.shape
    return ImageData(
        heights_nm=heights,
        width_nm=pitch_x * (columns - 1),
        length_nm=pitch_y * (rows - 1),
        width_pixels=columns,
        length_pixels=rows,
        pixel_pitch_x_nm=pitch_x,
        pixel_pitch_y_nm=pitch_y,
    )


def _synthetic_trench() -> ImageData:
    heights = np.full((100, 140), 20.0)
    heights[5:95, 50:66] = 10.0
    return _image(heights, pitch_x=2.0, pitch_y=1.5)


def test_two_trench_reference_dataset_matches_approved_ranges() -> None:
    image = read_csv(Path(__file__).parents[1] / "data" / "two-trenches.csv")

    trenches = analyze_trenches(image, _request())

    assert len(trenches) == 3
    assert all(70.0 <= trench.width_nm <= 78.0 for trench in trenches)
    assert all(501.0 <= trench.length_nm <= 503.0 for trench in trenches)
    assert 42.0 <= np.mean([trench.depth_nm for trench in trenches]) <= 47.0
    assert all(trench.footprint.shape == image.heights_nm.shape for trench in trenches)


def test_minimum_depth_boundary_includes_equal_depth_pixels() -> None:
    trenches = analyze_trenches(_synthetic_trench(), _request(depth=10.0))

    assert len(trenches) == 1
    assert trenches[0].depth_nm == pytest.approx(10.0)
    assert trenches[0].footprint.any()


def test_physical_measurements_are_rotation_invariant_with_anisotropic_pitch() -> None:
    image = _synthetic_trench()
    original = analyze_trenches(image, _request())
    rotated_heights = np.rot90(image.heights_nm)
    rotated = analyze_trenches(
        _image(
            rotated_heights,
            pitch_x=image.pixel_pitch_y_nm,
            pitch_y=image.pixel_pitch_x_nm,
        ),
        _request(),
    )

    assert len(original) == len(rotated) == 1
    np.testing.assert_allclose(
        [original[0].length_nm, original[0].width_nm, original[0].depth_nm],
        [rotated[0].length_nm, rotated[0].width_nm, rotated[0].depth_nm],
        atol=1e-10,
    )


def test_rejects_invalid_image_data() -> None:
    image = _image(np.full((5, 5), np.nan))

    with pytest.raises(ValueError, match="must all be finite"):
        analyze_trenches(image, _request())


def test_outliers_are_replaced_by_image_mean_before_detection() -> None:
    heights = np.zeros((10, 10))
    heights[0, 0] = 100.0

    filtered = _filter_outliers(heights)

    assert filtered[0, 0] == pytest.approx(1.0)
    assert np.count_nonzero(filtered) == 1


def test_round_low_region_is_rejected_by_aspect_ratio_filter() -> None:
    heights = np.full((100, 100), 20.0)
    heights[30:70, 30:70] = 10.0

    assert analyze_trenches(_image(heights), _request()) == []


def test_requires_trench_thresholds_in_effective_request() -> None:
    request = EffectiveRequest(feature_types=frozenset({FeatureType.TRENCH}))

    with pytest.raises(ValueError, match="must include trench thresholds"):
        analyze_trenches(_synthetic_trench(), request)
