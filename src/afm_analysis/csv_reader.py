"""Read metadata and height grids from the agreed AFM CSV format."""

from __future__ import annotations

import csv
from math import isfinite
from pathlib import Path

import numpy as np

from afm_analysis.models import ImageData

_REQUIRED_METADATA = {
    "ImageWidth",
    "ImageHeight",
    "ImageWidthPixel",
    "ImageHeightPixel",
    "ImageDataUnit",
}
_UNIT_TO_NM = {"m": 1e9, "nm": 1.0}


class CSVFormatError(ValueError):
    """Raised when an AFM CSV file does not match the supported format."""


def read_csv(path: str | Path) -> ImageData:
    """Read a metadata-prefixed AFM CSV into calibrated image data.

    Metadata rows use ``# Key,value`` syntax. Blank and comment lines are
    allowed before the matrix; the first non-comment row starts the matrix.
    Matrix rows are comma-separated finite numbers and must match the declared
    pixel dimensions. The image extent spans the first through last pixel, so
    pixel pitch is extent divided by pixel count minus one.
    """
    csv_path = Path(path)
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        lines = list(source)

    metadata: dict[str, str] = {}
    matrix_lines: list[str] = []
    matrix_started = False

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if not matrix_started and stripped.startswith("#"):
            payload = stripped[1:].strip()
            if not payload:
                continue
            fields = next(csv.reader([payload], skipinitialspace=True))
            if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
                raise CSVFormatError(
                    f"line {line_number}: metadata must use '# Key,value' syntax"
                )
            key, value = (field.strip() for field in fields)
            if key in metadata:
                raise CSVFormatError(f"line {line_number}: duplicate metadata key {key!r}")
            metadata[key] = value
            continue
        matrix_started = True
        if stripped.startswith("#"):
            raise CSVFormatError(f"line {line_number}: comments are only allowed before the matrix")
        matrix_lines.append(line)

    missing = _REQUIRED_METADATA - metadata.keys()
    if missing:
        raise CSVFormatError(f"missing metadata: {', '.join(sorted(missing))}")
    if not matrix_lines:
        raise CSVFormatError("height matrix is empty")

    unit = metadata["ImageDataUnit"]
    if unit not in _UNIT_TO_NM:
        raise CSVFormatError(f"unsupported ImageDataUnit {unit!r}; expected 'm' or 'nm'")
    scale = _UNIT_TO_NM[unit]

    width_nm = _positive_finite(metadata["ImageWidth"], "ImageWidth") * scale
    height_nm = _positive_finite(metadata["ImageHeight"], "ImageHeight") * scale
    width_pixels = _positive_integer(metadata["ImageWidthPixel"], "ImageWidthPixel")
    height_pixels = _positive_integer(metadata["ImageHeightPixel"], "ImageHeightPixel")
    if width_pixels < 2 or height_pixels < 2:
        raise CSVFormatError("ImageWidthPixel and ImageHeightPixel must both be at least 2")

    rows: list[tuple[float, ...]] = []
    for row_number, line in enumerate(matrix_lines, start=1):
        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error as error:
            raise CSVFormatError(f"matrix row {row_number}: malformed CSV row") from error
        if len(fields) != width_pixels:
            raise CSVFormatError(
                f"matrix row {row_number}: expected {width_pixels} values, found {len(fields)}"
            )
        values = tuple(
            _finite_number(value, f"matrix row {row_number}") * scale for value in fields
        )
        rows.append(values)

    if len(rows) != height_pixels:
        raise CSVFormatError(f"expected {height_pixels} matrix rows, found {len(rows)}")

    return ImageData(
        heights_nm=np.asarray(rows, dtype=np.float64),
        width_nm=width_nm,
        height_nm=height_nm,
        width_pixels=width_pixels,
        height_pixels=height_pixels,
        pixel_pitch_x_nm=width_nm / (width_pixels - 1),
        pixel_pitch_y_nm=height_nm / (height_pixels - 1),
    )


def _finite_number(value: str, name: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise CSVFormatError(f"{name}: {value!r} is not a number") from error
    if not isfinite(number):
        raise CSVFormatError(f"{name}: values must be finite")
    return number


def _positive_finite(value: str, name: str) -> float:
    number = _finite_number(value, name)
    if number <= 0:
        raise CSVFormatError(f"{name} must be positive")
    return number


def _positive_integer(value: str, name: str) -> int:
    number = _finite_number(value, name)
    if number <= 0 or not number.is_integer():
        raise CSVFormatError(f"{name} must be a positive integer")
    return int(number)
