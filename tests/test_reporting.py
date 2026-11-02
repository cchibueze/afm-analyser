"""Tests for operational run reporting."""

import logging
from pathlib import Path

import pytest

import afm_analysis.reporting as reporting
from afm_analysis.reporting import ReportingError, RunReporter


def test_records_categories_and_call_order_without_console_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with RunReporter() as reporter:
        reporter.progress("Reading image CSV")
        reporter.warning("Input has a small height range")
        reporter.error("Request is invalid")

    log_path = Path(reporting.__file__).resolve().parents[2] / "results" / "run.log"
    contents = log_path.read_text(encoding="utf-8").splitlines()
    assert len(contents) == 3
    assert "INFO     Progress: Reading image CSV" in contents[0]
    assert "WARNING  Warning: Input has a small height range" in contents[1]
    assert "ERROR    Error: Request is invalid" in contents[2]
    assert all(line[:19].count(":") == 2 for line in contents)
    assert capsys.readouterr() == ("", "")


def test_creates_results_directory_at_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reporting, "__file__", str(tmp_path / "src/afm_analysis/reporting.py"))

    with RunReporter() as reporter:
        reporter.progress("Started")

    assert (tmp_path / "results" / "run.log").is_file()


def test_setup_failure_is_printed_and_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(reporting, "__file__", str(tmp_path / "src/afm_analysis/reporting.py"))
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "run.log").mkdir()

    with pytest.raises(ReportingError, match="Unable to set up"):
        RunReporter()

    assert "Unable to set up run logfile" in capsys.readouterr().err


def test_write_failure_is_printed_and_raised(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RunReporter()

    def fail_emit(record: logging.LogRecord) -> None:
        raise OSError("disk full")

    reporter._handler.emit = fail_emit  # type: ignore[method-assign]
    with pytest.raises(ReportingError, match="Unable to write"):
        reporter.progress("Will fail")

    assert "disk full" in capsys.readouterr().err
    reporter.close()


def test_closed_reporter_rejects_new_messages() -> None:
    reporter = RunReporter()
    reporter.close()

    with pytest.raises(ReportingError, match="closed run reporter"):
        reporter.progress("Too late")


