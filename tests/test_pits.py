"""Production pit detection and measurement tests."""

from pathlib import Path

import numpy as np
import pytest

from afm_analysis.csv_reader import read_csv
from afm_analysis.models import EffectiveRequest, FeatureType, ImageData, PitThresholds
from afm_analysis.pits import _projected_area, analyze_pits
from afm_analysis.preprocessing import replace_local_extremes


def _request(depth: float = 4.0, diameter: float = 4.0) -> EffectiveRequest:
    return EffectiveRequest(
        feature_types=frozenset({FeatureType.PIT}),
        pit_thresholds=PitThresholds(depth, diameter),
    )


def _pit_image(pitch_x: float = 1.0, pitch_y: float = 1.0) -> ImageData:
    size = 40
    rows, columns = np.indices((size, size))
    distance = np.hypot(
        (columns - size // 2) * pitch_x,
        (rows - size // 2) * pitch_y,
    )
    normalized_distance = np.clip(distance / 10.0, 0.0, 1.0)
    heights = 10.0 * (
        3.0 * normalized_distance**2 - 2.0 * normalized_distance**3
    )
    return ImageData(
        heights_nm=heights,
        width_nm=pitch_x * (size - 1),
        length_nm=pitch_y * (size - 1),
        width_pixels=size,
        length_pixels=size,
        pixel_pitch_x_nm=pitch_x,
        pixel_pitch_y_nm=pitch_y,
    )


def test_supplied_reference_pit_matches_approved_ranges() -> None:
    image = read_csv(Path(__file__).parents[1] / "data" / "pit.csv")

    pits = analyze_pits(image, _request())

    assert len(pits) == 1
    assert 18.0 <= pits[0].diameter_nm <= 22.0
    assert -2.0 <= pits[0].centered_height_nm <= 2.0
    assert pits[0].aspect_ratio < 1.5


def test_pit_preprocessing_preserves_feature_heights_below_extreme_cutoff() -> None:
    image = read_csv(Path(__file__).parents[1] / "data" / "pit.csv")

    filtered = replace_local_extremes(image.heights_nm)

    np.testing.assert_array_equal(filtered, image.heights_nm)


def test_controlled_pit_is_detected_and_threshold_equality_passes() -> None:
    image = _pit_image()
    initial = analyze_pits(image, _request())

    assert len(initial) == 1
    equal_thresholds = _request(
        depth=initial[0].maximum_depth_nm,
        diameter=initial[0].diameter_nm,
    )
    accepted = analyze_pits(image, equal_thresholds)

    assert len(accepted) == 1
    assert accepted[0].maximum_depth_nm == pytest.approx(initial[0].maximum_depth_nm)
    assert accepted[0].diameter_nm == pytest.approx(initial[0].diameter_nm)


def test_measurements_are_rotation_invariant_with_anisotropic_spacing() -> None:
    image = _pit_image(pitch_x=1.5, pitch_y=1.0)
    original = analyze_pits(image, _request(depth=1.0, diameter=1.0))
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
    rotated = analyze_pits(rotated_image, _request(depth=1.0, diameter=1.0))

    assert len(original) == len(rotated) == 1
    np.testing.assert_allclose(
        [
            original[0].area_nm2,
            original[0].diameter_nm,
            original[0].maximum_depth_nm,
            original[0].aspect_ratio,
        ],
        [
            rotated[0].area_nm2,
            rotated[0].diameter_nm,
            rotated[0].maximum_depth_nm,
            rotated[0].aspect_ratio,
        ],
        atol=1e-10,
    )


def test_edge_pixel_cells_are_clipped_to_field_of_view() -> None: 
    footprint = np.ones((3, 4), dtype=bool)

    assert _projected_area(footprint, pitch_x=2.0, pitch_y=3.0) == pytest.approx(36.0)


def test_rejects_invalid_image_and_non_pit_request() -> None:
    image = _pit_image()
    invalid = ImageData(
        heights_nm=np.full((5, 5), np.nan),
        width_nm=4.0,
        length_nm=4.0,
        width_pixels=5,
        length_pixels=5,
        pixel_pitch_x_nm=1.0,
        pixel_pitch_y_nm=1.0,
    )
    no_pit = EffectiveRequest(feature_types=frozenset({FeatureType.TRENCH}))

    with pytest.raises(ValueError, match="must all be finite"):
        analyze_pits(invalid, _request())
    with pytest.raises(ValueError, match="must include pit thresholds"):
        analyze_pits(image, no_pit)



