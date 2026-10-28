from pathlib import Path
import numpy as np
import pytest

from trench_detection_skimage import Trench, load_afm_csv, measure_trenches, segment_low_regions


DATASET = Path(__file__).resolve().parents[2] / "data" / "interview_line_space_image.csv"


def analyze(
    heights: np.ndarray,
    spacing_i: float = 1.0,
    spacing_j: float = 1.0,
) -> tuple[float, list[Trench]]:
    _, labels, threshold = segment_low_regions(heights)
    return threshold, measure_trenches(labels, heights, spacing_i, spacing_j)


def test_scikit_image_loader_reads_supplied_dataset() -> None:
    image = load_afm_csv(DATASET)

    assert image.heights_nm.shape == (500, 500)
    assert np.isfinite(image.heights_nm).all()
    assert image.spacing_i_nm == image.spacing_j_nm == 1.0


def test_regionprops_detection_is_rotation_symmetric() -> None:
    heights = np.full((100, 120), 30.0)
    for start in (15, 55, 95):
        heights[:, start : start + 8] = 0.0

    _, original = analyze(heights)
    _, rotated = analyze(np.rot90(heights))

    assert len(original) == len(rotated) == 3
    np.testing.assert_allclose(
        [item.width_nm for item in original],
        [item.width_nm for item in rotated],
        atol=0.1,
    )
    np.testing.assert_allclose(
        [item.length_nm for item in original],
        [item.length_nm for item in rotated],
        atol=0.1,
    )


def test_regionprops_rectangular_estimates_match_supplied_sample() -> None:
    image = load_afm_csv(DATASET)
    threshold, trenches = analyze(image.heights_nm, image.spacing_i_nm, image.spacing_j_nm)

    assert 10.0 < threshold < 20.0
    assert len(trenches) == 3
    assert all(45.0 <= feature.width_nm <= 55.0 for feature in trenches)
    assert all(500.0 <= feature.length_nm <= 504.0 for feature in trenches)
    assert all(25.0 <= feature.depth_nm <= 35.0 for feature in trenches)
    assert [feature.center_j for feature in trenches] == sorted(
        feature.center_j for feature in trenches
    )


def test_csv_shape_mismatch_is_reported(tmp_path: Path) -> None:
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

    with pytest.raises(ValueError, match="does not match metadata"):
        load_afm_csv(malformed)
