"""Production bump detection and measurement tests."""

from pathlib import Path

import numpy as np
import pytest

from afm_analysis.bumps import analyze_bumps
from afm_analysis.csv_reader import read_csv
from afm_analysis.feature_geometry import projected_area
from afm_analysis.models import BumpThresholds, EffectiveRequest, FeatureType, ImageData


def _request(height: float = 4.0, diameter: float = 4.0) -> EffectiveRequest:
    return EffectiveRequest(
        feature_types=frozenset({FeatureType.BUMP}),
        bump_thresholds=BumpThresholds(height, diameter),
    )


def _bump_image(pitch_x: float = 1.0, pitch_y: float = 1.0) -> ImageData: #ASK CODEX
    size = 40
    rows, columns = np.indices((size, size))
    distance = np.hypot(
        (columns - size // 2) * pitch_x,
        (rows - size // 2) * pitch_y,
    )
    normalized_distance = np.clip(distance / 10.0, 0.0, 1.0)
    heights = 10.0 * (1.0 - 3.0 * normalized_distance**2 + 2.0 * normalized_distance**3)
    return ImageData(
        heights_nm=heights,
        width_nm=pitch_x * (size - 1),
        length_nm=pitch_y * (size - 1),
        width_pixels=size,
        length_pixels=size,
        pixel_pitch_x_nm=pitch_x,
        pixel_pitch_y_nm=pitch_y,
    )


def test_supplied_reference_bump_matches_approved_ranges() -> None:
    image = read_csv(Path(__file__).parents[1] / "data" / "bump.csv")

    bumps = analyze_bumps(image, _request())

    assert len(bumps) == 1
    assert 18.0 <= bumps[0].diameter_nm <= 22.0
    assert 3.0 <= bumps[0].centered_height_nm <= 7.0
    assert bumps[0].aspect_ratio < 1.5


def test_controlled_bump_is_detected_and_threshold_equality_passes() -> None:
    image = _bump_image()
    initial = analyze_bumps(image, _request())

    assert len(initial) == 1
    equal_thresholds = _request(
        height=initial[0].maximum_height_nm,
        diameter=initial[0].diameter_nm,
    )
    accepted = analyze_bumps(image, equal_thresholds)

    assert len(accepted) == 1
    assert accepted[0].maximum_height_nm == pytest.approx(initial[0].maximum_height_nm)
    assert accepted[0].diameter_nm == pytest.approx(initial[0].diameter_nm)
    assert not analyze_bumps(
        image, _request(height=initial[0].maximum_height_nm + 0.01)
    )
    assert not analyze_bumps(
        image, _request(diameter=initial[0].diameter_nm + 0.01)
    )


def test_measurements_are_rotation_invariant_with_anisotropic_spacing() -> None:
    image = _bump_image(pitch_x=1.5, pitch_y=1.0)
    original = analyze_bumps(image, _request(height=1.0, diameter=1.0))
    rotated_heights = np.rot90(image.heights_nm)
    rotated_image = ImageData(
        heights_nm=rotated_heights,
        width_nm=image.length_nm,
        length_nm=image.width_nm,
        width_pixels=rotated_heights.shape[1],
        length_pixels=rotated_heights.shape[0],
        pixel_pitch_x_nm=image.pixel_pitch_y_nm,
        pixel_pitch_y_nm=image.pixel_pitch_x_nm,
    )
    rotated = analyze_bumps(rotated_image, _request(height=1.0, diameter=1.0))

    assert len(original) == len(rotated) == 1
    np.testing.assert_allclose(
        [
            original[0].area_nm2,
            original[0].diameter_nm,
            original[0].maximum_height_nm,
            original[0].aspect_ratio,
        ],
        [
            rotated[0].area_nm2,
            rotated[0].diameter_nm,
            rotated[0].maximum_height_nm,
            rotated[0].aspect_ratio,
        ],
        atol=1e-10,
    )


def test_edge_pixel_cells_are_clipped_to_field_of_view() -> None: #ASK CODEX
    footprint = np.ones((3, 4), dtype=bool)

    assert projected_area(footprint, pitch_x=2.0, pitch_y=3.0) == pytest.approx(36.0)


def test_rejects_invalid_image_and_non_bump_request() -> None:
    image = _bump_image()
    invalid = ImageData(
        heights_nm=np.full((5, 5), np.nan),
        width_nm=4.0,
        length_nm=4.0,
        width_pixels=5,
        length_pixels=5,
        pixel_pitch_x_nm=1.0,
        pixel_pitch_y_nm=1.0,
    )
    no_bump = EffectiveRequest(feature_types=frozenset({FeatureType.TRENCH}))

    with pytest.raises(ValueError, match="must all be finite"):
        analyze_bumps(invalid, _request())
    with pytest.raises(ValueError, match="must include bump thresholds"):
        analyze_bumps(image, no_bump)
