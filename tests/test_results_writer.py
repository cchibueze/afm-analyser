"""Tests for plain-text analysis results."""

from pathlib import Path

import numpy as np
import pytest

from afm_analysis.models import (
    BumpResult,
    BumpThresholds,
    EffectiveRequest,
    FeatureType,
    ImageData,
    PitResult,
    PitThresholds,
    SelectedCandidates,
    TrenchResult,
    TrenchThresholds,
)
from afm_analysis.results_writer import ResultsWriteError, format_results, write_results


def _image() -> ImageData:
    return ImageData(np.zeros((5, 7)), 12.0, 8.0, 7, 5, 2.0, 2.0)


def _request() -> EffectiveRequest:
    return EffectiveRequest(
        frozenset(FeatureType),
        TrenchThresholds(5, 3, 6),
        BumpThresholds(4, 4),
        PitThresholds(4, 4),
    )


def _empty() -> SelectedCandidates:
    return SelectedCandidates([], [], [])


def _at_centroid(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    footprint = np.zeros(shape, dtype=bool)
    for row, column in points:
        footprint[row, column] = True
    return footprint


def test_zero_feature_output_exact() -> None:
    assert format_results(_image(), _request(), _empty(), "/tmp/run.log") == (
        "AFM Analysis Results\n"
        "Image dimensions: 5 rows × 7 columns\n"
        "Image size: X=12 nm, Y=8 nm\n"
        "Log file: /tmp/run.log\n"
        "\nCalculation choices\n"
        "Feature types: trench, bump, pit\n"
        "Trench thresholds: depth >= 5 nm, width >= 3 nm, length >= 6 nm\n"
        "Bump thresholds: height >= 4 nm, diameter >= 4 nm\n"
        "Pit thresholds: depth >= 4 nm, diameter >= 4 nm\n"
        "\nCounts\nTrenches: 0\nPits: 0\nBumps: 0\n"
        "\nTrenches\n\nPits\n\nBumps\n"
    )


def test_one_of_each_feature_and_centroid_units() -> None:
    selected = SelectedCandidates(
        [
            TrenchResult(
                _at_centroid((5, 7), [(0, 2), (0, 3), (2, 2), (2, 3)]),
                6,
                3,
                5,
                2.5,
                1.0,
            )
        ],
        [
            PitResult(
                _at_centroid((5, 7), [(1, 1), (1, 2), (3, 1), (3, 2)]),
                10,
                3,
                4,
                1,
                1,
                1.5,
                2.0,
            )
        ],
        [BumpResult(_at_centroid((5, 7), [(0, 3), (1, 3)]), 12, 4, 6, 2, 1, 3.0, 0.5)],
    )

    output = format_results(_image(), _request(), selected, "run.log")

    assert "Trenches: 1\nPits: 1\nBumps: 1" in output
    assert (
        "Trench 1: centroid x=2.5, y=1 pixels (0-based); x=5 nm, y=2 nm; "
        "length=6 nm, width=3 nm, depth=5 nm"
    ) in output
    assert (
        "Pit 1: centroid x=1.5, y=2 pixels (0-based); x=3 nm, y=4 nm; "
        "projected area=10 nm², maximum depth=4 nm"
    ) in output
    assert (
        "Bump 1: centroid x=3, y=0.5 pixels (0-based); x=6 nm, y=1 nm; "
        "projected area=12 nm², maximum height=6 nm"
    ) in output


def test_multiple_features_are_type_indexed_in_input_order() -> None:
    selected = SelectedCandidates(
        [
            TrenchResult(np.ones((1, 1), dtype=bool), 6, 3, 5, 0, 0),
            TrenchResult(np.ones((1, 1), dtype=bool), 7, 3, 5, 0, 0),
        ],
        [],
        [],
    )
    output = format_results(_image(), _request(), selected, "run.log")

    assert "Trenches: 2\nPits: 0\nBumps: 0" in output
    assert "Trench 1:" in output
    assert "Trench 2:" in output


@pytest.mark.parametrize(
    "factory",
    [
        lambda mask: TrenchResult(mask, 1, 1, 1, 0, 0),
        lambda mask: PitResult(mask, 1, 1, 1, 1, 1, 0, 0),
        lambda mask: BumpResult(mask, 1, 1, 1, 1, 1, 0, 0),
    ],
)
def test_feature_result_rejects_centroid_that_disagrees_with_footprint(factory) -> None:
    footprint = _at_centroid((2, 2), [(0, 1), (1, 1)])

    with pytest.raises(ValueError, match="centroid must match"):
        factory(footprint)


def test_optional_operational_details_are_appended_verbatim() -> None:
    output = format_results(_image(), _request(), _empty(), "run.log", ["Warning: noisy image"])

    assert output.endswith("\nAnalysis details\nWarning: noisy image\n")


def test_write_failure_raises_results_write_error(tmp_path: Path) -> None:
    destination = tmp_path / "missing" / "results.txt"

    with pytest.raises(ResultsWriteError, match="Unable to write results file"):
        write_results(destination, _image(), _request(), _empty(), "run.log")


def test_write_results_creates_exact_text(tmp_path: Path) -> None:
    path = tmp_path / "results.txt"
    expected = format_results(_image(), _request(), _empty(), "run.log")

    write_results(path, _image(), _request(), _empty(), "run.log")

    assert path.read_text(encoding="utf-8") == expected
