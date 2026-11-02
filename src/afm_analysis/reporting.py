"""Operational reporting for an AFM analysis run."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import TracebackType


class ReportingError(RuntimeError):
    """Raised when operational messages cannot be written to the logfile."""


class _RaisingFileHandler(logging.FileHandler):
    """File handler that exposes I/O errors instead of swallowing them."""

    def emit(self, record: logging.LogRecord) -> None:
        if self.stream is None:
            self.stream = self._open()
        message = self.format(record)
        self.stream.write(f"{message}{self.terminator}")
        self.flush()


class RunReporter:
    """Write progress, warnings, and errors to the run logfile."""

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        log_path = project_root / "results" / "run.log"
        logger = logging.Logger(f"afm_analysis.run.{id(self)}", level=logging.INFO)
        logger.propagate = False
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = _RaisingFileHandler(log_path, mode="w", encoding="utf-8")
        except OSError as error:
            message = f"Unable to set up run logfile at {log_path}: {error}"
            print(message, file=sys.stderr)
            raise ReportingError(message) from error

        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        self._logger = logger
        self._handler = handler
        self._closed = False

    def progress(self, message: str) -> None:
        """Record a progress message."""
        self._report(logging.INFO, "Progress", message)

    def warning(self, message: str) -> None:
        """Record a warning."""
        self._report(logging.WARNING, "Warning", message)

    def error(self, message: str) -> None:
        """Record an error."""
        self._report(logging.ERROR, "Error", message)

    def _report(self, level: int, category: str, message: str) -> None:
        if self._closed:
            raise ReportingError("Cannot write to a closed run reporter")
        try:
            self._logger.log(level, "%s: %s", category, message)
        except OSError as error:
            diagnostic = f"Unable to write to run logfile: {error}"
            print(diagnostic, file=sys.stderr)
            raise ReportingError(diagnostic) from error

    def close(self) -> None:
        """Close the logfile and release its handler."""
        if not self._closed:
            self._logger.removeHandler(self._handler)
            self._handler.close()
            self._closed = True

    def __enter__(self) -> RunReporter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
