"""Command-line interface for validating AFM analysis requests."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from afm_analysis.models import EffectiveRequest, FeatureType
from afm_analysis.reporting import ReportingError, RunReporter
from afm_analysis.requests import Request, validate_request


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
    """Build the argument parser for the request-validation CLI."""
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
    """Validate an operator request; analysis is intentionally not run here."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        reporter = RunReporter()
    except ReportingError:
        return 2
    try:
        with reporter:
            reporter.progress("Run started")
            try:
                request_from_args(args)
            except ValueError as error:
                print(f"{parser.prog}: error: {error}", file=sys.stderr)
                reporter.error(str(error))
                return 2
    except ReportingError:
        # The reporter has already printed its failure diagnostic to stderr.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
