"""Command line interface for f1-telemetry-charts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.validation import ConfigValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="f1tc",
        description="Generate consistent F1 analysis chart packages.",
    )
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser(
        "config",
        help="Configuration utilities.",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    validate_parser = config_subparsers.add_parser(
        "validate",
        help="Validate a framework configuration file.",
    )
    validate_parser.add_argument("path", type=Path, help="Configuration file path.")
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable validation result.",
    )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a chart package from a configuration file.",
    )
    generate_parser.add_argument("path", type=Path, help="Configuration file path.")
    generate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable generation result.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config" and args.config_command == "validate":
        return _validate_config_command(args.path, json_output=args.json)
    if args.command == "generate":
        return _generate_command(args.path, json_output=args.json)

    parser.print_help()
    return 0


def _generate_command(path: Path, *, json_output: bool) -> int:
    try:
        config = load_config(path)
        result = run_analysis(config)
    except ConfigValidationError as exc:
        if json_output:
            print(
                json.dumps(
                    {
                        "status": "invalid",
                        "errors": [issue.to_dict() for issue in exc.issues],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("Configuration is invalid.")
            for issue in exc.issues:
                print(f"- {issue.path}: {issue.message}")
        return 1
    except Exception as exc:
        if json_output:
            print(json.dumps({"status": "failed", "errors": [str(exc)]}, indent=2))
        else:
            print(f"Generation failed: {exc}")
        return 1

    payload = {
        "status": result.status,
        "output_dir": str(result.output_dir),
        "manifest_path": str(result.manifest_path),
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Generation status: {result.status}")
        print(f"Output directory: {result.output_dir}")
        print(f"Manifest: {result.manifest_path}")
    return 0 if result.status in {"succeeded", "partially_succeeded"} else 1


def _validate_config_command(path: Path, *, json_output: bool) -> int:
    try:
        config = load_config(path)
    except ConfigValidationError as exc:
        if json_output:
            print(
                json.dumps(
                    {
                        "status": "invalid",
                        "errors": [issue.to_dict() for issue in exc.issues],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("Configuration is invalid.")
            for issue in exc.issues:
                print(f"- {issue.path}: {issue.message}")
        return 1

    result = {
        "status": "valid",
        "schema_version": config.schema_version,
        "recipes": [recipe.recipe_id for recipe in config.recipes],
        "output_dir": str(config.output_dir),
    }
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Configuration is valid.")
        print(f"Schema version: {config.schema_version}")
        print(f"Recipes: {', '.join(result['recipes'])}")
        print(f"Output directory: {result['output_dir']}")
    return 0
