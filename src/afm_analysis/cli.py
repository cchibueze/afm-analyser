"""Command-line interface for AFM image analysis."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from afm_analysis.bumps import analyze_bumps
from afm_analysis.csv_reader import read_csv
from afm_analysis.models import EffectiveRequest, FeatureType
from afm_analysis.pits import analyze_pits
from afm_analysis.plotting import write_overview_plot
from afm_analysis.reporting import ReportingError, RunReporter
from afm_analysis.requests import Request, validate_request
from afm_analysis.results_writer import ResultsWriteError, write_results
from afm_analysis.selection import select_candidates
from afm_analysis.trenches import analyze_trenches


def _feature_list(value: str) -> list[str]:
    """Parse a comma-separated feature selection without hiding empty entries."""
    features = [item.strip() for item in value.split(",")]
    if not all(features):
        raise argparse.ArgumentTypeError("features must be comma-separated feature names")
    allowed = {feature.value for feature in FeatureType}
    unknown = [feature for feature in features if feature not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"unsupported feature type: {unknown[0]}")
    return features


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the analysis CLI."""
    parser = argparse.ArgumentParser(prog="afm-analysis")
    parser.add_argument(
        "--path",
        type=Path,
        required=True,
        metavar="PATH",
        help="path to the AFM image CSV file",
    )
    parser.add_argument(
        "--features",
        type=_feature_list,
        metavar="FEATURES",
        help="comma-separated feature names: trench, bump, pit (default: trench)",
    )
    parser.add_argument("--trench-depth-nm", type=float)
    parser.add_argument("--trench-width-nm", type=float)
    parser.add_argument("--trench-length-nm", type=float)
    parser.add_argument("--bump-height-nm", type=float)
    parser.add_argument("--bump-diameter-nm", type=float)
    parser.add_argument("--pit-depth-nm", type=float)
    parser.add_argument("--pit-diameter-nm", type=float)
    parser.add_argument("--output", type=Path, default=Path("results/output"), metavar="PATH")
    parser.add_argument("--plot", action="store_true", help="write an overview PNG")
    parser.add_argument(
        "--include-details", action="store_true", help="include operational details in results"
    )
    return parser


def request_from_args(args: argparse.Namespace) -> EffectiveRequest:
    """Convert parsed CLI options to the validated request model."""
    feature_types = args.features
    selected = (
        {FeatureType(value) for value in feature_types}
        if feature_types is not None
        else {FeatureType.TRENCH}
    )
    thresholds_by_feature = {
        FeatureType.TRENCH: (args.trench_depth_nm, args.trench_width_nm, args.trench_length_nm),
        FeatureType.BUMP: (args.bump_height_nm, args.bump_diameter_nm),
        FeatureType.PIT: (args.pit_depth_nm, args.pit_diameter_nm),
    }
    for feature, values in thresholds_by_feature.items():
        if any(value is not None for value in values) and feature not in selected:
            raise ValueError(f"{feature.value} thresholds require selecting {feature.value}")

    return validate_request(
        Request(
            feature_types=feature_types,
            trench_depth_nm=args.trench_depth_nm,
            trench_width_nm=args.trench_width_nm,
            trench_length_nm=args.trench_length_nm,
            bump_height_nm=args.bump_height_nm,
            bump_diameter_nm=args.bump_diameter_nm,
            pit_depth_nm=args.pit_depth_nm,
            pit_diameter_nm=args.pit_diameter_nm,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested analysis and write its outputs."""
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path: Path = args.output
    results_dir = Path("results")
    log_path = results_dir / f"{output_path.stem}.log"
    plot_path = results_dir / f"{output_path.stem}.png"
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        reporter = RunReporter(log_path)
    except ReportingError:
        return 2
    except OSError as error:
        print(f"{parser.prog}: error: unable to prepare output paths: {error}", file=sys.stderr)
        return 2
    try:
        with reporter:
            reporter.progress("Run started")
            try:
                request = request_from_args(args)
                reporter.progress(f"Reading image CSV: {args.path}")
                image = read_csv(args.path)
                trenches = analyze_trenches(image, request) if request.trench_thresholds else []
                pits = analyze_pits(image, request) if request.pit_thresholds else []
                bumps = analyze_bumps(image, request) if request.bump_thresholds else []
                selected = select_candidates(image, request, trenches, pits, bumps)
                reporter.progress("Analysis and feature selection complete")
                details = (
                    log_path.read_text(encoding="utf-8").splitlines()
                    if args.include_details
                    else None
                )
                try:
                    write_results(output_path, image, request, selected, log_path, details)
                except ResultsWriteError:
                    _preserve_partial_output(output_path)
                    raise
                if args.plot:
                    write_overview_plot(plot_path, image, selected)
                reporter.progress("Run completed")
            except (ImportError, OSError, ValueError, RuntimeError) as error:
                message = str(error)
                print(f"{parser.prog}: error: {message}", file=sys.stderr)
                reporter.error(message)
                return 2
    except ReportingError:
        # The reporter has already printed its failure diagnostic to stderr.
        return 2
    return 0


def _preserve_partial_output(path: Path) -> None:
    """Copy a partial results file to its crash artifact and remove the original."""
    if not path.exists():
        return
    crash_path = Path("results") / f"{path.stem}.crash"
    try:
        shutil.copyfile(path, crash_path)
        path.unlink()
    except OSError as error:
        print(f"afm-analysis: error: unable to preserve partial output: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
