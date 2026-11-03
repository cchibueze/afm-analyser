#!/usr/bin/env python3
"""Exploratory trench detector for the supplied AFM CSV example.

The CSV exporter stores a metadata preamble followed by a rectangular height
matrix. Its stated image dimensions are treated as full field-of-view lengths;
pixel-center spacing is therefore width/(pixel_count - 1). This prototype
assumes the physical dimension metadata is in meters and converts heights and
distances to nanometers.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
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
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class ImageData:
    """Height grid and physical metadata, with heights expressed in nm."""

    heights_nm: FloatArray
    width_nm: float
    height_nm: float
    spacing_i_nm: float
    spacing_j_nm: float


@dataclass(frozen=True)
class Trench:
    """One segmented elongated low region and its exploratory measurements."""

    index: int
    center_i: float
    center_j: float
    width_nm: float
    visible_length_nm: float
    depth_nm: float
    pixel_count: int
    bounds_ij: tuple[tuple[int, int], tuple[int, int]]


def load_afm_csv(path: Path) -> ImageData:
    """Read the metadata preamble and numeric height matrix from an AFM CSV."""
    metadata: dict[str, str] = {}
    matrix_rows: list[list[float]] = []
    in_matrix = False

    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        for line_number, row in enumerate(csv.reader(csv_file), start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if not in_matrix and row[0].strip().startswith("#"):
                if len(row) >= 2 and row[0].strip() != "#":
                    metadata[row[0].strip()[1:].strip()] = row[1].strip()
                continue
            in_matrix = True
            try:
                matrix_rows.append([float(cell.strip()) for cell in row])
            except ValueError as error:
                raise ValueError(
                    f"CSV line {line_number} contains a non-numeric matrix value"
                ) from error

    required = (
        "ImageWidth",
        "ImageHeight",
        "ImageWidthPixel",
        "ImageHeightPixel",
        "ImageDataUnit",
    )
    missing = [key for key in required if key not in metadata]
    if missing:
        raise ValueError(f"CSV metadata is missing required fields: {', '.join(missing)}")
    if not matrix_rows:
        raise ValueError("CSV does not contain a height matrix")

    row_lengths = {len(row) for row in matrix_rows}
    if len(row_lengths) != 1:
        raise ValueError("CSV height matrix rows have inconsistent column counts")

    heights_input = np.asarray(matrix_rows, dtype=np.float64)
    if not np.isfinite(heights_input).all():
        raise ValueError("CSV height matrix contains non-finite values")

    try:
        expected_pixels_i = int(metadata["ImageHeightPixel"])
        expected_pixels_j = int(metadata["ImageWidthPixel"])
        width_m = float(metadata["ImageWidth"])
        height_m = float(metadata["ImageHeight"])
    except ValueError as error:
        raise ValueError("CSV pixel dimensions and physical dimensions must be numeric") from error

    if heights_input.shape != (expected_pixels_i, expected_pixels_j):
        raise ValueError(
            "CSV matrix shape does not match metadata: "
            f"found {heights_input.shape}, expected {(expected_pixels_i, expected_pixels_j)}"
        )
    if expected_pixels_i < 2 or expected_pixels_j < 2:
        raise ValueError("At least two pixels per axis are required to derive spacing")
    if width_m <= 0 or height_m <= 0:
        raise ValueError("Physical image dimensions must be positive")

    unit = metadata["ImageDataUnit"].strip().lower()
    height_scale = {"m": 1e9, "nm": 1.0}.get(unit)
    if height_scale is None:
        raise ValueError(f"Unsupported ImageDataUnit {metadata['ImageDataUnit']!r}; use m or nm")

    return ImageData(
        heights_nm=heights_input * height_scale,
        width_nm=width_m * 1e9,
        height_nm=height_m * 1e9,
        spacing_i_nm=(height_m * 1e9) / (expected_pixels_i - 1),
        spacing_j_nm=(width_m * 1e9) / (expected_pixels_j - 1),
    )


def detect_candidate_mask(
    heights_nm: FloatArray,
    threshold_nm: float | None = None,
    gap_close_radius_pixels: int = 1,
) -> tuple[BoolArray, float]:
    """Segment globally low pixels and close only small gaps in their mask."""
    threshold = float(threshold_otsu(heights_nm)) if threshold_nm is None else threshold_nm
    mask = heights_nm < threshold
    if gap_close_radius_pixels < 0:
        raise ValueError("gap_close_radius_pixels cannot be negative")
    if gap_close_radius_pixels:
        footprint = footprint_rectangle((2 * gap_close_radius_pixels + 1,) * 2)
        mask = closing(mask, footprint=footprint, mode="ignore")
    return np.asarray(mask, dtype=bool), float(threshold)


def _measure_region(
    label_mask: BoolArray,
    heights_nm: FloatArray,
    spacing_i_nm: float,
    spacing_j_nm: float,
) -> tuple[float, float, float, int, tuple[tuple[int, int], tuple[int, int]]]:
    """Measure a region by PCA-oriented cross-sections and a binned centerline."""
    coordinates = np.argwhere(label_mask).astype(np.float64)
    center = coordinates.mean(axis=0)
    centered = coordinates - center
    physical = centered * np.array([spacing_i_nm, spacing_j_nm])
    covariance = physical.T @ physical / max(len(coordinates), 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    # Convert pixel coordinates to physical coordinates before projecting, so
    # anisotropic input pixels are handled correctly.
    unit_major = eigenvectors[:, int(np.argmax(eigenvalues))]
    unit_major /= np.linalg.norm(unit_major)
    unit_minor = np.array([-unit_major[1], unit_major[0]])
    along = physical @ unit_major
    across = physical @ unit_minor

    bin_width = min(spacing_i_nm, spacing_j_nm)
    bins = np.floor((along - along.min()) / bin_width).astype(int)
    centerline: list[np.ndarray] = []
    widths: list[float] = []
    bin_counts: list[int] = []
    for bin_index in np.unique(bins):
        in_bin = bins == bin_index
        centerline.append(np.array([float(np.mean(along[in_bin])), float(np.mean(across[in_bin]))]))
        bin_counts.append(int(in_bin.sum()))
        if int(in_bin.sum()) > 1:
            widths.append(float(np.quantile(across[in_bin], 0.975) - np.quantile(across[in_bin], 0.025)))
        else:
            widths.append(bin_width)
    centerline_points = np.asarray(centerline)
    width_nm = float(np.median(widths))

    # The first and last PCA bins are often clipped corners where a trench
    # meets the image boundary. Fit the centerline through the middle sections
    # and intersect that line with the image rectangle. This gives an
    # orientation-aware end-to-end length without counting pixel-edge jitter.
    counts = np.asarray(bin_counts)
    if len(centerline_points) > 1:
        central_counts = counts[max(0, len(counts) // 10) : max(1, 9 * len(counts) // 10)]
        typical_count = float(np.median(central_counts))
        complete = counts >= max(2.0, 0.5 * typical_count)
        retained = centerline_points[complete]
        if len(retained) < 3:
            retained = centerline_points
        # Exclude clipped ends from the line fit, but retain enough interior
        # points to average over small bends and segmentation irregularities.
        fit_start = len(retained) // 10
        fit_stop = max(fit_start + 2, 9 * len(retained) // 10)
        fit_points = retained[fit_start:fit_stop]
        slope, intercept = np.polyfit(fit_points[:, 0], fit_points[:, 1], deg=1)
        fitted_direction = unit_major + slope * unit_minor
        fitted_direction /= np.linalg.norm(fitted_direction)
        line_origin = center * np.array([spacing_i_nm, spacing_j_nm]) + intercept * unit_minor

        # Find where the fitted centerline crosses the pixel-center rectangle.
        limits = np.array(
            [
                [0.0, (heights_nm.shape[0] - 1) * spacing_i_nm],
                [0.0, (heights_nm.shape[1] - 1) * spacing_j_nm],
            ]
        )
        intersections: list[np.ndarray] = []
        for axis in range(2):
            if abs(fitted_direction[axis]) < 1e-12:
                continue
            for bound in limits[axis]:
                distance = (bound - line_origin[axis]) / fitted_direction[axis]
                point = line_origin + distance * fitted_direction
                other_axis = 1 - axis
                if limits[other_axis, 0] - 1e-6 <= point[other_axis] <= limits[other_axis, 1] + 1e-6:
                    intersections.append(point)
        if len(intersections) >= 2:
            length_nm = float(
                max(np.linalg.norm(first - second) for i, first in enumerate(intersections) for second in intersections[i + 1 :])
            )
        else:
            length_nm = float(np.ptp(retained[:, 0]))
    else:
        length_nm = 0.0

    region_heights = heights_nm[label_mask]
    # Use a thin surrounding shell for a local surface reference; exclude all
    # thresholded low pixels so adjacent trenches cannot lower the baseline.
    shell = dilation(label_mask, footprint=footprint_rectangle((11, 11)), mode="ignore") & ~label_mask
    shell &= heights_nm >= np.median(heights_nm)
    reference_height = float(np.median(heights_nm[shell])) if shell.any() else float(np.median(heights_nm))
    depth_nm = reference_height - float(np.median(region_heights))

    indices = np.argwhere(label_mask)
    bounds = (
        (int(indices[:, 0].min()), int(indices[:, 0].max())),
        (int(indices[:, 1].min()), int(indices[:, 1].max())),
    )
    return width_nm, length_nm, depth_nm, len(coordinates), bounds


def measure_trenches(
    candidate_mask: BoolArray,
    heights_nm: FloatArray,
    spacing_i_nm: float,
    spacing_j_nm: float,
    minimum_aspect_ratio: float = 3.0,
    minimum_span_fraction: float = 0.7,
) -> list[Trench]:
    """Label low regions and retain elongated candidates spanning the image."""
    labels = label(candidate_mask, connectivity=2)
    regions = regionprops(
        labels,
        intensity_image=heights_nm,
        spacing=(spacing_i_nm, spacing_j_nm),
    )
    candidates: list[tuple[tuple[float, float], Trench]] = []
    max_length_nm = max(
        heights_nm.shape[0] * spacing_i_nm,
        heights_nm.shape[1] * spacing_j_nm,
    )
    for region_properties in regions:
        if region_properties.num_pixels < 50:
            continue
        region = labels == region_properties.label
        width_nm, length_nm, depth_nm, pixel_count, bounds = _measure_region(
            region, heights_nm, spacing_i_nm, spacing_j_nm
        )
        # RegionProperties supplies rotation-independent ellipse axes for a
        # concise first-pass shape filter. Final width remains cross-section
        # based because equivalent-ellipse width is only a shape proxy.
        if region_properties.axis_minor_length <= 0 or (
            region_properties.axis_major_length / region_properties.axis_minor_length
            < minimum_aspect_ratio
        ):
            continue
        if length_nm < minimum_span_fraction * max_length_nm:
            continue
        center_i, center_j = (
            float(region_properties.centroid[0] / spacing_i_nm),
            float(region_properties.centroid[1] / spacing_j_nm),
        )
        candidates.append(
            (
                (center_j, center_i),
                Trench(
                    index=0,
                    center_i=center_i,
                    center_j=center_j,
                    width_nm=width_nm,
                    visible_length_nm=length_nm,
                    depth_nm=depth_nm,
                    pixel_count=pixel_count,
                    bounds_ij=bounds,
                ),
            )
        )
    candidates.sort(key=lambda item: item[0])
    return [replace(trench, index=i) for i, (_, trench) in enumerate(candidates, 1)]


def write_outputs(
    image: ImageData,
    mask: BoolArray,
    trenches: Sequence[Trench],
    threshold_nm: float,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write an ij-coordinate overlay plot and machine-readable JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "trench_detection_overlay.png"
    summary_path = output_dir / "trench_detection_summary.json"

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    # Transpose for plotting so the horizontal axis is i and the vertical axis j.
    shown = axes[0].imshow(image.heights_nm.T, origin="lower", cmap="viridis")
    axes[0].set_title("AFM height (nm)")
    axes[0].set_xlabel("i grid coordinate (pixel index)")
    axes[0].set_ylabel("j grid coordinate (pixel index)")
    fig.colorbar(shown, ax=axes[0], label="Height (nm)")

    axes[1].imshow(mask.T, origin="lower", cmap="gray_r", interpolation="nearest")
    axes[1].set_title(f"Low-region mask (threshold {threshold_nm:.2f} nm)")
    axes[1].set_xlabel("i grid coordinate (pixel index)")
    axes[1].set_ylabel("j grid coordinate (pixel index)")
    for trench in trenches:
        axes[0].plot(trench.center_i, trench.center_j, "r+", markersize=11, markeredgewidth=2)
        axes[0].text(trench.center_i + 4, trench.center_j + 4, str(trench.index), color="white")
        axes[1].plot(trench.center_i, trench.center_j, "r+")
        axes[1].text(trench.center_i + 4, trench.center_j + 4, str(trench.index), color="red")
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)

    summary = {
        "input_assumptions": {
            "height_unit_from_metadata": "m converted to nm",
            "physical_image_dimensions_unit": "m",
            "pixel_spacing_convention": "full field of view divided by pixel_count - 1",
            "coordinate_convention": "zero-based (i, j); each CSV line is a matrix row",
        },
        "grid_shape_ij": list(image.heights_nm.shape),
        "height_range_nm": [float(image.heights_nm.min()), float(image.heights_nm.max())],
        "pixel_spacing_nm": {"i": image.spacing_i_nm, "j": image.spacing_j_nm},
        "threshold_nm": threshold_nm,
        "candidate_count": len(trenches),
        "trenches": [asdict(trench) for trench in trenches],
        "outputs": {"plot": plot_path.name, "summary": summary_path.name},
        "measurement_note": (
            "Length is the end-to-end chord of a fitted centerline intersected with "
            "the image boundary. It accounts for trench angle; it does not add arc "
            "length for curvature, and trench continuation outside the field is unknown."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return plot_path, summary_path


def run(input_path: Path, output_dir: Path, threshold_nm: float | None = None) -> list[Trench]:
    """Run the detector and write its inspectable outputs."""
    image = load_afm_csv(input_path)
    mask, effective_threshold = detect_candidate_mask(image.heights_nm, threshold_nm)
    trenches = measure_trenches(mask, image.heights_nm, image.spacing_i_nm, image.spacing_j_nm)
    write_outputs(image, mask, trenches, effective_threshold, output_dir)
    return trenches


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_input = Path(__file__).resolve().parents[2] / "data" / "trenches.csv"
    parser.add_argument("--input", type=Path, default=default_input, help="AFM metadata-plus-matrix CSV")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "trench_detection_output",
    )
    parser.add_argument("--threshold-nm", type=float, default=None, help="Override global Otsu threshold")
    args = parser.parse_args(argv)
    trenches = run(args.input, args.output_dir, args.threshold_nm)
    print(f"Detected {len(trenches)} trench candidates")
    print(f"Results: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
