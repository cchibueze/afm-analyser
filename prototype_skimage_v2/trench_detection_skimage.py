#!/usr/bin/env python3
"""Short AFM trench prototype built around scikit-image measurements."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from math import sqrt
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import closing, dilation, footprint_rectangle


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int32]
BoolArray = NDArray[np.bool_]

RECTANGLE_MOMENT_CORRECTION = sqrt(3.0) / 2.0


@dataclass(frozen=True)
class ImageData:
    heights_nm: FloatArray
    spacing_i_nm: float
    spacing_j_nm: float


@dataclass(frozen=True)
class Trench:
    index: int
    center_i: float
    center_j: float
    width_nm: float
    length_nm: float
    depth_nm: float
    orientation_rad: float
    ellipse_minor_axis_nm: float
    ellipse_major_axis_nm: float
    pixel_count: int
    bounds_ij: tuple[tuple[int, int], tuple[int, int]]


def load_afm_csv(path: Path) -> ImageData:
    """Read this export's metadata preamble and height matrix; convert to nm."""
    metadata: dict[str, str] = {}
    rows: list[list[float]] = []
    in_matrix = False
    with path.open(newline="", encoding="utf-8-sig") as source:
        for line_number, row in enumerate(csv.reader(source), start=1):
            if not row or not any(value.strip() for value in row):
                continue
            if not in_matrix and row[0].strip().startswith("#"):
                if row[0].strip() != "#" and len(row) > 1:
                    metadata[row[0].strip()[1:].strip()] = row[1].strip()
                continue
            in_matrix = True
            try:
                rows.append([float(value) for value in row])
            except ValueError as error:
                raise ValueError(f"Non-numeric height at CSV line {line_number}") from error

    required = ("ImageWidth", "ImageHeight", "ImageWidthPixel", "ImageHeightPixel", "ImageDataUnit")
    missing = [key for key in required if key not in metadata]
    if missing:
        raise ValueError(f"Missing CSV metadata: {', '.join(missing)}")
    if not rows or len({len(row) for row in rows}) != 1:
        raise ValueError("CSV must contain a non-empty rectangular height matrix")

    try:
        matrix = np.asarray(rows, dtype=np.float64)
        pixel_i, pixel_j = int(metadata["ImageHeightPixel"]), int(metadata["ImageWidthPixel"])
        height_m, width_m = float(metadata["ImageHeight"]), float(metadata["ImageWidth"])
    except ValueError as error:
        raise ValueError("CSV dimensions and matrix values must be numeric") from error
    if matrix.shape != (pixel_i, pixel_j):
        raise ValueError(f"Matrix shape {matrix.shape} does not match metadata {(pixel_i, pixel_j)}")
    if pixel_i < 2 or pixel_j < 2 or width_m <= 0 or height_m <= 0:
        raise ValueError("Image dimensions must be positive and each axis needs at least two pixels")
    if not np.isfinite(matrix).all():
        raise ValueError("Height matrix contains non-finite values")

    unit = metadata["ImageDataUnit"].lower()
    if unit not in {"m", "nm"}:
        raise ValueError(f"Unsupported ImageDataUnit {unit!r}; this prototype accepts m or nm")
    matrix *= 1e9 if unit == "m" else 1.0
    return ImageData(
        heights_nm=matrix,
        spacing_i_nm=height_m * 1e9 / (pixel_i - 1),
        spacing_j_nm=width_m * 1e9 / (pixel_j - 1),
    )


def segment_low_regions(
    heights_nm: FloatArray,
    threshold_nm: float | None = None,
    closing_radius_pixels: int = 1,
) -> tuple[BoolArray, IntArray, float]:
    """Threshold low pixels, close one-pixel gaps, and label 8-connected regions."""
    threshold = float(threshold_otsu(heights_nm)) if threshold_nm is None else threshold_nm
    mask = heights_nm < threshold
    if closing_radius_pixels < 0:
        raise ValueError("closing_radius_pixels cannot be negative")
    if closing_radius_pixels:
        width = 2 * closing_radius_pixels + 1
        mask = closing(mask, footprint=footprint_rectangle((width, width)), mode="ignore")
    labels = label(mask, connectivity=2)
    return np.asarray(mask, dtype=bool), labels, float(threshold)


def measure_trenches(
    labels: IntArray,
    heights_nm: FloatArray,
    spacing_i_nm: float,
    spacing_j_nm: float,
    minimum_aspect_ratio: float = 3.0,
    minimum_span_fraction: float = 0.7,
) -> list[Trench]:
    """Use regionprops shape moments as rectangle-corrected size estimates."""
    regions = regionprops(
        labels,
        intensity_image=heights_nm,
        spacing=(spacing_i_nm, spacing_j_nm),
    )
    minimum_length_nm = minimum_span_fraction * max(
        (heights_nm.shape[0] - 1) * spacing_i_nm,
        (heights_nm.shape[1] - 1) * spacing_j_nm,
    )
    global_median = float(np.median(heights_nm))
    shell_footprint = footprint_rectangle((11, 11))
    candidates: list[Trench] = []

    for region in regions:
        major = float(region.axis_major_length)
        minor = float(region.axis_minor_length)
        if region.num_pixels < 50 or minor <= 0 or major / minor < minimum_aspect_ratio:
            continue
        length_nm = major * RECTANGLE_MOMENT_CORRECTION
        width_nm = minor * RECTANGLE_MOMENT_CORRECTION
        if length_nm < minimum_length_nm:
            continue

        region_mask = labels == region.label
        surrounding = dilation(region_mask, footprint=shell_footprint, mode="ignore") & ~region_mask
        surrounding &= heights_nm >= global_median
        reference_nm = float(np.median(heights_nm[surrounding])) if surrounding.any() else global_median
        center_i = float(region.centroid[0] / spacing_i_nm)
        center_j = float(region.centroid[1] / spacing_j_nm)
        min_i, min_j, max_i, max_j = region.bbox
        candidates.append(
            Trench(
                index=0,
                center_i=center_i,
                center_j=center_j,
                width_nm=width_nm,
                length_nm=length_nm,
                depth_nm=reference_nm - float(region.intensity_median),
                orientation_rad=float(region.orientation),
                ellipse_minor_axis_nm=minor,
                ellipse_major_axis_nm=major,
                pixel_count=int(region.num_pixels),
                bounds_ij=((min_i, max_i - 1), (min_j, max_j - 1)),
            )
        )

    candidates.sort(key=lambda trench: (trench.center_j, trench.center_i))
    return [Trench(**(asdict(candidate) | {"index": index})) for index, candidate in enumerate(candidates, 1)]


def write_outputs(
    image: ImageData,
    mask: BoolArray,
    trenches: Sequence[Trench],
    threshold_nm: float,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write a height/mask review plot and a JSON measurement summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "trench_detection_overlay.png"
    summary_path = output_dir / "trench_detection_summary.json"

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    height_plot = axes[0].imshow(image.heights_nm.T, origin="lower", cmap="viridis")
    axes[0].set_title("AFM height (nm)")
    axes[0].set_xlabel("i grid coordinate (pixel index)")
    axes[0].set_ylabel("j grid coordinate (pixel index)")
    fig.colorbar(height_plot, ax=axes[0], label="Height (nm)")
    axes[1].imshow(mask.T, origin="lower", cmap="gray_r", interpolation="nearest")
    axes[1].set_title(f"Low-region mask (threshold {threshold_nm:.2f} nm)")
    axes[1].set_xlabel("i grid coordinate (pixel index)")
    axes[1].set_ylabel("j grid coordinate (pixel index)")
    for trench in trenches:
        for axis in axes:
            axis.plot(trench.center_i, trench.center_j, "r+", markersize=10)
            axis.text(trench.center_i + 4, trench.center_j + 4, str(trench.index), color="red")
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)

    summary = {
        "method": "Otsu threshold + morphology closing + connected regions + regionprops",
        "grid_shape_ij": list(image.heights_nm.shape),
        "height_range_nm": [float(image.heights_nm.min()), float(image.heights_nm.max())],
        "pixel_spacing_nm": {"i": image.spacing_i_nm, "j": image.spacing_j_nm},
        "threshold_nm": threshold_nm,
        "candidate_count": len(trenches),
        "measurements": [asdict(trench) for trench in trenches],
        "dimension_assumption": (
            "regionprops axis lengths describe an equivalent ellipse; multiplying by "
            "sqrt(3)/2 estimates the sides of a uniformly filled rectangular band."
        ),
        "depth_assumption": "Median height of an adjacent high-valued shell minus median region height.",
        "outputs": {"plot": plot_path.name, "summary": summary_path.name},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return plot_path, summary_path


def run(input_path: Path, output_dir: Path, threshold_nm: float | None = None) -> list[Trench]:
    image = load_afm_csv(input_path)
    mask, labels, threshold = segment_low_regions(image.heights_nm, threshold_nm)
    trenches = measure_trenches(labels, image.heights_nm, image.spacing_i_nm, image.spacing_j_nm)
    write_outputs(image, mask, trenches, threshold, output_dir)
    return trenches


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    project_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--input", type=Path, default=project_root / "interview_line_space_image.csv")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--threshold-nm", type=float, default=None)
    args = parser.parse_args(argv)
    trenches = run(args.input, args.output_dir, args.threshold_nm)
    print(f"Detected {len(trenches)} candidates; results: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
