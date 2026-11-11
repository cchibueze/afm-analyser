"""Tests for CLI argument conversion and request validation."""

from __future__ import annotations

import argparse
import sys

import pytest

from afm_analysis.cli import build_parser, main, request_from_args
from afm_analysis.models import FeatureType
from afm_analysis.reporting import ReportingError


def _parse(*arguments: str) -> argparse.Namespace:
    return build_parser().parse_args(arguments)


def test_cli_defaults_to_trenches_and_default_thresholds() -> None:
    effective = request_from_args(_parse("--path", "image.csv"))

    assert effective.feature_types == frozenset({FeatureType.TRENCH})
    assert effective.trench_thresholds is not None
    assert effective.trench_thresholds.depth_nm == 5.0
    assert effective.trench_thresholds.width_nm == 3.0
    assert effective.trench_thresholds.length_nm == 6.0


def test_cli_accepts_feature_and_threshold_overrides() -> None:
    effective = request_from_args(
        _parse(
            "--path=image.csv",
            "--features",
            "bump,pit",
            "--bump-height-nm",
            "8",
            "--bump-diameter-nm",
            "5",
            "--pit-depth-nm",
            "7",
        )
    )

    assert effective.feature_types == frozenset({FeatureType.BUMP, FeatureType.PIT})
    assert effective.bump_thresholds is not None
    assert effective.bump_thresholds.height_nm == 8.0
    assert effective.bump_thresholds.diameter_nm == 5.0
    assert effective.pit_thresholds is not None
    assert effective.pit_thresholds.depth_nm == 7.0


def test_cli_rejects_thresholds_for_unselected_features() -> None:
    with pytest.raises(ValueError, match="pit thresholds require selecting pit"):
        request_from_args(_parse("--path", "image.csv", "--pit-depth-nm", "4"))


@pytest.mark.parametrize("features", ["ridge", "trench,,pit", ",pit", "pit,"])
def test_cli_rejects_invalid_feature_names_or_list_syntax(features: str) -> None:
    with pytest.raises(SystemExit) as error:
        _parse("--path", "image.csv", "--features", features)
    assert error.value.code == 2


@pytest.mark.parametrize("value", ["0", "-1", "inf", "nan"])
def test_cli_rejects_invalid_threshold_values(value: str) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        request_from_args(_parse("--path", "image.csv", "--trench-depth-nm", value))


def test_cli_rejects_trench_ratio_below_minimum() -> None:
    with pytest.raises(ValueError, match="at least 1.5 times"):
        request_from_args(
            _parse("--path", "image.csv", "--trench-width-nm", "4", "--trench-length-nm", "5.9")
        )


def test_cli_missing_path_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main([])

    assert error.value.code == 2
    assert "--path" in capsys.readouterr().err


def test_cli_invalid_request_returns_two_and_reports_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = main(["--path", "image.csv", "--trench-depth-nm", "0"])

    assert status == 2
    captured = capsys.readouterr()
    assert "positive finite" in captured.err
    assert captured.out == ""


def test_cli_success_returns_zero_without_console_output(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "image.csv"
    image.write_text(
        "# ImageWidth,4\n# ImageHeight,4\n# ImageWidthPixel,3\n"
        "# ImageHeightPixel,3\n# ImageDataUnit,nm\n0,0,0\n0,0,0\n0,0,0\n",
        encoding="utf-8",
    )
    assert main(["--path", str(image), "--features", "bump", "--bump-height-nm", "100"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert (tmp_path / "results" / "output").is_file()
    assert (tmp_path / "results" / "output.log").is_file()
    assert not (tmp_path / "results" / "output.png").exists()


def test_cli_returns_two_when_reporter_write_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingReporter:
        def __init__(self, log_path=None) -> None:
            self.log_path = log_path

        def __enter__(self) -> FailingReporter:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def progress(self, message: str) -> None:
            print("Unable to write to run logfile: disk full", file=sys.stderr)
            raise ReportingError("Unable to write to run logfile: disk full")

    monkeypatch.setattr("afm_analysis.cli.RunReporter", FailingReporter)

    assert main(["--path", "image.csv"]) == 2
    assert capsys.readouterr().err.count("Unable to write to run logfile") == 1


