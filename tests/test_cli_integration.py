"""End-to-end checks for CLI orchestration and generated files."""

from pathlib import Path

import pytest

import afm_analysis.cli as cli
from afm_analysis.results_writer import ResultsWriteError


def _csv(path: Path) -> None:
    path.write_text(
        "# ImageWidth,4\n# ImageHeight,4\n# ImageWidthPixel,3\n"
        "# ImageHeightPixel,3\n# ImageDataUnit,nm\n0,0,0\n0,0,0\n0,0,0\n",
        encoding="utf-8",
    )


def test_cli_writes_custom_results_log_plot_and_optional_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "image.csv"
    _csv(image)

    status = cli.main(
        [
            "--path",
            str(image),
            "--features",
            "bump",
            "--bump-height-nm",
            "100",
            "--output",
            "results/sample.txt",
            "--plot",
            "--include-details",
        ]
    )

    assert status == 0
    assert capsys.readouterr() == ("", "")
    result = (tmp_path / "results" / "sample.txt").read_text(encoding="utf-8")
    log_path = tmp_path / "results" / "sample.log"
    assert "Log file: results/sample.log" in result
    assert "Bumps: 0" in result
    assert "Analysis details" in result
    assert log_path.is_file()
    plot = tmp_path / "results" / "sample.png"
    assert plot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_invalid_csv_returns_error_and_keeps_log_without_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "bad.csv"
    image.write_text("not an AFM table\n", encoding="utf-8")

    assert cli.main(["--path", str(image)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "missing metadata" in captured.err
    assert "ERROR    Error:" in (tmp_path / "results" / "output.log").read_text(
        encoding="utf-8"
    )
    assert not (tmp_path / "results" / "output").exists()


def test_partial_results_are_copied_to_crash_file_and_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "image.csv"
    _csv(image)

    def partial_failure(path, *args, **kwargs) -> None:
        Path(path).write_text("partial result", encoding="utf-8")
        raise ResultsWriteError("simulated write failure")

    monkeypatch.setattr(cli, "write_results", partial_failure)
    assert cli.main(["--path", str(image)]) == 2

    assert capsys.readouterr().out == ""
    assert not (tmp_path / "results" / "output").exists()
    assert (tmp_path / "results" / "output.crash").read_text(encoding="utf-8") == (
        "partial result"
    )
