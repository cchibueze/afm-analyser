"""Small synthetic masks make candidate selection geometry explicit."""

from collections.abc import Callable

import numpy as np
import pytest

from afm_analysis import selection
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


def _image(heights: np.ndarray | None = None) -> ImageData:
    if heights is None:
        heights = np.zeros((20, 20), dtype=float)
    return ImageData(heights, 19, 19, 20, 20, 1, 1)


def _request(
    *,
    trench: TrenchThresholds | None = None,
    bump: BumpThresholds | None = None,
    pit: PitThresholds | None = None,
) -> EffectiveRequest:
    return EffectiveRequest(
        frozenset(FeatureType),
        trench or TrenchThresholds(0, 0, 0),
        bump or BumpThresholds(0, 0),
        pit or PitThresholds(0, 0),
    )


def _trench(mask: np.ndarray) -> TrenchResult:
    centroid_y, centroid_x = np.argwhere(mask).mean(axis=0)
    return TrenchResult(mask, 1, 1, 1, centroid_x, centroid_y)


def _pit(mask: np.ndarray) -> PitResult:
    centroid_y, centroid_x = np.argwhere(mask).mean(axis=0)
    return PitResult(mask, 999, 999, 999, 999, 999, centroid_x, centroid_y)


def _bump(mask: np.ndarray) -> BumpResult:
    centroid_y, centroid_x = np.argwhere(mask).mean(axis=0)
    return BumpResult(mask, 999, 999, 999, 999, 999, centroid_x, centroid_y)


def _select(
    trenches=(),
    pits=(),
    bumps=(),
    *,
    image: ImageData | None = None,
    request: EffectiveRequest | None = None,
) -> SelectedCandidates:
    return selection.select_candidates(
        image or _image(),
        request or _request(),
        list(trenches),
        list(pits),
        list(bumps),
    )


def _bypass_remeasurement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep overlap tests focused on priority rather than shape measurements."""
    monkeypatch.setattr(selection, "_remeasure_trenches", lambda image, request, items: items)
    monkeypatch.setattr(selection, "_remeasure_pits", lambda image, request, items: items)
    monkeypatch.setattr(selection, "_remeasure_bumps", lambda image, request, items: items)


def _mask(*coordinates: tuple[int, int]) -> np.ndarray:
    result = np.zeros((20, 20), dtype=bool)
    for row, column in coordinates:
        result[row, column] = True
    return result


def test_diagonal_same_type_candidates_merge_transitively_and_are_remeasured() -> None:
    first = np.zeros((20, 20), dtype=bool)
    first[4:7, 7:10] = True
    second = np.zeros_like(first)
    second[7:10, 4:7] = True
    third = np.zeros_like(first)
    third[10:13, 7:10] = True
    fourth = np.zeros_like(first)
    fourth[7:10, 10:13] = True
    heights = np.zeros((20, 20), dtype=float)
    heights[first | second | third | fourth] = 10

    result = _select(
        bumps=[_bump(fourth), _bump(third), _bump(first), _bump(second)],
        image=_image(heights),
    )

    assert len(result.bumps) == 1
    np.testing.assert_array_equal(result.bumps[0].footprint, first | second | third | fourth)
    assert result.bumps[0].maximum_height_nm == pytest.approx(10)
    assert result.bumps[0].area_nm2 != 999


def test_merged_bump_passes_diameter_threshold_that_each_part_would_fail() -> None:
    first = np.zeros((20, 20), dtype=bool)
    first[4:7, 4:7] = True
    second = np.zeros_like(first)
    second[5:8, 5:8] = True
    merged = first | second
    heights = np.zeros((20, 20), dtype=float)
    heights[merged] = 10
    # Each 3x3 part has diameter below 4 nm; their merged area passes it.
    request = _request(bump=BumpThresholds(height_nm=5, diameter_nm=4))

    result = _select(bumps=[_bump(first), _bump(second)], image=_image(heights), request=request)

    assert len(result.bumps) == 1
    np.testing.assert_array_equal(result.bumps[0].footprint, merged)
    assert result.bumps[0].maximum_height_nm == pytest.approx(10)
    assert result.bumps[0].diameter_nm >= 4


def test_merged_pit_passes_diameter_threshold_that_each_part_would_fail() -> None:
    first = np.zeros((20, 20), dtype=bool)
    first[4:7, 4:7] = True
    second = np.zeros_like(first)
    second[5:8, 5:8] = True
    merged = first | second
    heights = np.zeros((20, 20), dtype=float)
    heights[merged] = -10
    request = _request(pit=PitThresholds(depth_nm=5, diameter_nm=4))

    result = _select(pits=[_pit(first), _pit(second)], image=_image(heights), request=request)

    assert len(result.pits) == 1
    np.testing.assert_array_equal(result.pits[0].footprint, merged)
    assert result.pits[0].maximum_depth_nm == pytest.approx(10)
    assert result.pits[0].diameter_nm >= 4


def test_merged_trench_measurements_are_recomputed_from_union() -> None:
    first = np.zeros((20, 20), dtype=bool)
    first[2:10, 4:7] = True
    second = np.zeros_like(first)
    second[10:18, 7:10] = True
    merged = first | second
    heights = np.zeros((20, 20), dtype=float)
    heights[merged] = -10
    request = _request(trench=TrenchThresholds(depth_nm=5, width_nm=0, length_nm=0))

    result = _select(
        trenches=[_trench(first), _trench(second)],
        image=_image(heights),
        request=request,
    )

    assert len(result.trenches) == 1
    np.testing.assert_array_equal(result.trenches[0].footprint, merged)
    assert result.trenches[0].depth_nm == pytest.approx(10)
    assert result.trenches[0].length_nm > 1
    assert result.trenches[0].width_nm > 1


def test_disjoint_same_type_candidates_remain_separate_and_centroid_sorted() -> None:
    left = np.zeros((20, 20), dtype=bool)
    left[3:5, 3:5] = True
    right = np.zeros_like(left)
    right[12:14, 12:14] = True

    result = _select(bumps=[_bump(right), _bump(left)])

    assert len(result.bumps) == 2
    np.testing.assert_array_equal(result.bumps[0].footprint, left)
    np.testing.assert_array_equal(result.bumps[1].footprint, right)


def test_exactly_80_percent_overlap_suppresses_lower_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bypass_remeasurement(monkeypatch)
    shared = _mask((5, 5), (5, 6), (5, 7), (5, 8))
    larger = shared.copy()
    larger[6, 5] = True
    # Four shared cells / five union cells = exactly 80%.

    result = _select(pits=[_pit(shared)], bumps=[_bump(larger)])

    assert len(result.pits) == 1
    assert result.bumps == []


def test_overlap_below_80_percent_keeps_both_types(monkeypatch: pytest.MonkeyPatch) -> None:
    _bypass_remeasurement(monkeypatch)
    first = _mask((5, 5), (5, 6), (5, 7), (5, 8))
    second = _mask((5, 7), (5, 8), (5, 9), (5, 10))
    # Two shared cells / six union cells is below 80%.

    result = _select(pits=[_pit(first)], bumps=[_bump(second)])

    assert len(result.pits) == 1
    assert len(result.bumps) == 1


def test_touch_without_shared_area_does_not_suppress(monkeypatch: pytest.MonkeyPatch) -> None:
    _bypass_remeasurement(monkeypatch)
    first = _mask((5, 5))
    diagonal_neighbor = _mask((6, 6))

    result = _select(pits=[_pit(first)], bumps=[_bump(diagonal_neighbor)])

    assert len(result.pits) == 1
    assert len(result.bumps) == 1


@pytest.mark.parametrize(
    ("higher_type", "lower_type"),
    [
        (FeatureType.TRENCH, FeatureType.PIT),
        (FeatureType.TRENCH, FeatureType.BUMP),
        (FeatureType.PIT, FeatureType.BUMP),
    ],
)
def test_each_priority_pair_keeps_the_higher_type(
    monkeypatch: pytest.MonkeyPatch,
    higher_type: FeatureType,
    lower_type: FeatureType,
) -> None:
    _bypass_remeasurement(monkeypatch)
    footprint = np.zeros((20, 20), dtype=bool)
    footprint[5:9, 5:9] = True
    make_candidate: dict[FeatureType, Callable[[np.ndarray], object]] = {
        FeatureType.TRENCH: _trench,
        FeatureType.PIT: _pit,
        FeatureType.BUMP: _bump,
    }
    candidate_lists = {FeatureType.TRENCH: [], FeatureType.PIT: [], FeatureType.BUMP: []}
    candidate_lists[higher_type] = [make_candidate[higher_type](footprint)]
    candidate_lists[lower_type] = [make_candidate[lower_type](footprint)]

    result = _select(
        trenches=candidate_lists[FeatureType.TRENCH],
        pits=candidate_lists[FeatureType.PIT],
        bumps=candidate_lists[FeatureType.BUMP],
    )

    result_lists = {
        FeatureType.TRENCH: result.trenches,
        FeatureType.PIT: result.pits,
        FeatureType.BUMP: result.bumps,
    }
    assert len(result_lists[higher_type]) == 1
    assert result_lists[lower_type] == []


def test_three_type_conflict_keeps_only_trench(monkeypatch: pytest.MonkeyPatch) -> None:
    _bypass_remeasurement(monkeypatch)
    footprint = np.zeros((20, 20), dtype=bool)
    footprint[5:9, 5:9] = True

    result = _select(
        trenches=[_trench(footprint)],
        pits=[_pit(footprint)],
        bumps=[_bump(footprint)],
    )

    assert len(result.trenches) == 1
    assert result.pits == []
    assert result.bumps == []


def test_selected_results_are_in_separate_centroid_sorted_lists() -> None:
    trench_mask = np.zeros((20, 20), dtype=bool)
    trench_mask[2:14, 7:9] = True
    early = np.zeros((20, 20), dtype=bool)
    early[2:4, 2:4] = True
    late = np.zeros_like(early)
    late[15:17, 15:17] = True
    pit_mask = np.zeros_like(early)
    pit_mask[11:13, 15:17] = True

    result = _select(
        trenches=[_trench(trench_mask)],
        pits=[_pit(pit_mask)],
        bumps=[_bump(late), _bump(early)],
    )

    assert len(result.trenches) == 1
    assert len(result.pits) == 1
    assert len(result.bumps) == 2
    np.testing.assert_array_equal(result.bumps[0].footprint, early)
    np.testing.assert_array_equal(result.bumps[1].footprint, late)
