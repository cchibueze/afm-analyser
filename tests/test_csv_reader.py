"""Tests for the production AFM CSV reader."""

from pathlib import Path

import numpy as np
import pytest

from afm_analysis.csv_reader import CSVFormatError, read_csv


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "image.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_reads_metadata_and_converts_values_and_pitch_from_meters(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        """# DPVersion, 0.133.0
#
# ImageWidth,4.000000E-9
# ImageHeight,6.000000E-9
# ImageWidthPixel,5
# ImageHeightPixel,4
# ImageDataUnit,m
#
1.0e-9,2.0e-9,3.0e-9,4.0e-9,5.0e-9
-1.0e-9,0,1.0e-9,2.0e-9,3.0e-9
0,0,0,0,0
5.0e-9,4.0e-9,3.0e-9,2.0e-9,1.0e-9
""",
    )

    image = read_csv(path)

    assert image.width_nm == pytest.approx(4.0)
    assert image.height_nm == pytest.approx(6.0)
    assert image.width_pixels == 5
    assert image.height_pixels == 4
    assert image.pixel_pitch_x_nm == pytest.approx(1.0)
    assert image.pixel_pitch_y_nm == pytest.approx(2.0)
    assert isinstance(image.heights_nm, np.ndarray)
    assert image.heights_nm.dtype == np.float64
    assert image.heights_nm.shape == (4, 5)
    assert image.heights_nm[0] == pytest.approx((1.0, 2.0, 3.0, 4.0, 5.0))
    assert image.heights_nm[1][0] == pytest.approx(-1.0)


def test_reads_nanometer_input_without_scaling(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        """# ImageWidth,4
# ImageHeight,6
# ImageWidthPixel,3
# ImageHeightPixel,3
# ImageDataUnit,nm
1,2,3
4,5,6
7,8,9
""",
    )

    image = read_csv(path)

    np.testing.assert_array_equal(image.heights_nm[2], (7.0, 8.0, 9.0))
    assert image.pixel_pitch_x_nm == pytest.approx(2.0)
    assert image.pixel_pitch_y_nm == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("# ImageWidth,1\n", "missing metadata"),
        (
            "# ImageWidth,1\n# ImageHeight,1\n# ImageWidthPixel,2\n"
            "# ImageHeightPixel,2\n# ImageDataUnit,um\n1,2\n3,4\n",
            "unsupported ImageDataUnit",
        ),
        (
            "# ImageWidth,1\n# ImageHeight,1\n# ImageWidthPixel,2\n"
            "# ImageHeightPixel,2\n# ImageDataUnit,nm\n1,2\n3\n",
            "expected 2 values",
        ),
        (
            "# ImageWidth,1\n# ImageHeight,1\n# ImageWidthPixel,2\n"
            "# ImageHeightPixel,2\n# ImageDataUnit,nm\n1,nan\n3,4\n",
            "finite",
        ),
        (
            "# ImageWidth,1\n# ImageHeight,1\n# ImageWidthPixel,2\n"
            "# ImageHeightPixel,2\n# ImageDataUnit,nm\n1,2\n",
            "expected 2 matrix rows, found 1",
        ),
        (
            "# ImageWidth,1\n# ImageHeight,1\n# ImageWidthPixel,1\n"
            "# ImageHeightPixel,2\n# ImageDataUnit,nm\n1\n2\n",
            "at least 2",
        ),
    ],
)
def test_rejects_invalid_csv(content: str, message: str, tmp_path: Path) -> None:
    with pytest.raises(CSVFormatError, match=message):
        read_csv(_write_csv(tmp_path, content))


def test_supplied_sample_has_one_nanometer_pixel_pitch() -> None:
    sample = Path(__file__).parents[1] / "data" / "interview_line_space_image.csv"

    image = read_csv(sample)

    assert image.width_pixels == 500
    assert image.height_pixels == 500
    assert image.pixel_pitch_x_nm == pytest.approx(1.0)
    assert image.pixel_pitch_y_nm == pytest.approx(1.0)
