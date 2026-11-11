"""Plain-text results formatting and writing."""

from __future__ import annotations

from pathlib import Path

from afm_analysis.models import EffectiveRequest, FeatureType, ImageData, SelectedCandidates


class ResultsWriteError(RuntimeError):
    """Raised when the results file cannot be written."""


def _number(value: float) -> str:
    return f"{value:.6g}"


def format_results(
    image: ImageData,
    request: EffectiveRequest,
    results: SelectedCandidates,
    logfile_path: str | Path,
    operational_details: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Format measured results; this function performs no scientific calculations."""
    lines = [
        "AFM Analysis Results",
        f"Image dimensions: {image.length_pixels} rows × {image.width_pixels} columns",
        f"Image size: X={_number(image.width_nm)} nm, Y={_number(image.length_nm)} nm",
        f"Log file: {logfile_path}",
        "",
        "Calculation choices",
        "Feature types: " + ", ".join(
            feature.value
            for feature in (FeatureType.TRENCH, FeatureType.BUMP, FeatureType.PIT)
            if feature in request.feature_types
        ),
    ]
    if request.trench_thresholds is not None:
        threshold = request.trench_thresholds
        lines.append(
            "Trench thresholds: "
            f"depth >= {_number(threshold.depth_nm)} nm, "
            f"width >= {_number(threshold.width_nm)} nm, "
            f"length >= {_number(threshold.length_nm)} nm"
        )
    if request.bump_thresholds is not None:
        threshold = request.bump_thresholds
        lines.append(
            "Bump thresholds: "
            f"height >= {_number(threshold.height_nm)} nm, "
            f"diameter >= {_number(threshold.diameter_nm)} nm"
        )
    if request.pit_thresholds is not None:
        threshold = request.pit_thresholds
        lines.append(
            "Pit thresholds: "
            f"depth >= {_number(threshold.depth_nm)} nm, "
            f"diameter >= {_number(threshold.diameter_nm)} nm"
        )

    lines.extend(
        [
            "",
            "Counts",
            f"Trenches: {len(results.trenches)}",
            f"Pits: {len(results.pits)}",
            f"Bumps: {len(results.bumps)}",
            "",
            "Trenches",
        ]
    )
    for index, feature in enumerate(results.trenches, start=1):
        x_nm = feature.centroid_x_pixel * image.pixel_pitch_x_nm
        y_nm = feature.centroid_y_pixel * image.pixel_pitch_y_nm
        lines.append(
            f"Trench {index}: centroid x={_number(feature.centroid_x_pixel)}, "
            f"y={_number(feature.centroid_y_pixel)} pixels (0-based); "
            f"x={_number(x_nm)} nm, y={_number(y_nm)} nm; "
            f"length={_number(feature.length_nm)} nm, "
            f"width={_number(feature.width_nm)} nm, depth={_number(feature.depth_nm)} nm"
        )

    lines.extend(["", "Pits"])
    for index, feature in enumerate(results.pits, start=1):
        x_nm = feature.centroid_x_pixel * image.pixel_pitch_x_nm
        y_nm = feature.centroid_y_pixel * image.pixel_pitch_y_nm
        lines.append(
            f"Pit {index}: centroid x={_number(feature.centroid_x_pixel)}, "
            f"y={_number(feature.centroid_y_pixel)} pixels (0-based); "
            f"x={_number(x_nm)} nm, y={_number(y_nm)} nm; "
            f"projected area={_number(feature.area_nm2)} nm², "
            f"maximum depth={_number(feature.maximum_depth_nm)} nm"
        )

    lines.extend(["", "Bumps"])
    for index, feature in enumerate(results.bumps, start=1):
        x_nm = feature.centroid_x_pixel * image.pixel_pitch_x_nm
        y_nm = feature.centroid_y_pixel * image.pixel_pitch_y_nm
        lines.append(
            f"Bump {index}: centroid x={_number(feature.centroid_x_pixel)}, "
            f"y={_number(feature.centroid_y_pixel)} pixels (0-based); "
            f"x={_number(x_nm)} nm, y={_number(y_nm)} nm; "
            f"projected area={_number(feature.area_nm2)} nm², "
            f"maximum height={_number(feature.maximum_height_nm)} nm"
        )

    if operational_details:
        lines.extend(["", "Analysis details", *operational_details])
    return "\n".join(lines) + "\n"


def write_results(
    path: str | Path,
    image: ImageData,
    request: EffectiveRequest,
    results: SelectedCandidates,
    logfile_path: str | Path,
    operational_details: list[str] | tuple[str, ...] | None = None,
) -> None:
    """Write formatted results to a UTF-8 plain-text file."""
    output_path = Path(path)
    try:
        output_path.write_text(
            format_results(image, request, results, logfile_path, operational_details),
            encoding="utf-8",
        )
    except OSError as error:
        message = f"Unable to write results file at {output_path}: {error}"
        raise ResultsWriteError(message) from error
