"""Command line interface for f1-telemetry-charts."""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path
from typing import Sequence

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.validation import ConfigValidationError
from f1_telemetry_charts.preview.reader import PackagePreviewError, read_package_view


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

    preview_parser = subparsers.add_parser(
        "preview",
        help="Start the local package preview UI.",
    )
    preview_parser.add_argument(
        "package_path",
        type=Path,
        nargs="?",
        help="Generated package directory to open initially.",
    )
    preview_parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    preview_parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    preview_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser automatically.",
    )
    preview_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate launch options and package input without starting the server.",
    )
    preview_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable preview launch result.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config" and args.config_command == "validate":
        return _validate_config_command(args.path, json_output=args.json)
    if args.command == "generate":
        return _generate_command(args.path, json_output=args.json)
    if args.command == "preview":
        return _preview_command(
            args.package_path,
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
            check_only=args.check_only,
            json_output=args.json,
        )

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
        "observations_path": str(result.observations_path)
        if result.observations_path
        else None,
        "review_path": str(result.review_path) if result.review_path else None,
        "markdown_path": str(result.markdown_path) if result.markdown_path else None,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Generation status: {result.status}")
        print(f"Output directory: {result.output_dir}")
        print(f"Manifest: {result.manifest_path}")
        if result.observations_path:
            print(f"Observations: {result.observations_path}")
        if result.review_path:
            print(f"Review metadata: {result.review_path}")
        if result.markdown_path:
            print(f"Markdown draft: {result.markdown_path}")
    return 0 if result.status in {"succeeded", "partially_succeeded"} else 1


def _preview_command(
    package_path: Path | None,
    *,
    host: str,
    port: int,
    open_browser: bool,
    check_only: bool,
    json_output: bool,
) -> int:
    url = f"http://{host}:{port}"
    if package_path is not None:
        try:
            view = read_package_view(package_path)
        except PackagePreviewError as exc:
            if json_output:
                print(json.dumps({"status": "invalid", "errors": [str(exc)]}, indent=2))
            else:
                print(f"Package preview failed: {exc}")
            return 1
        package_path = Path(view.package_path)

    payload = {
        "status": "ready" if check_only else "starting",
        "url": url,
        "package_path": str(package_path) if package_path else None,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Preview URL: {url}")
        if package_path:
            print(f"Package: {package_path}")

    if check_only:
        return 0

    from f1_telemetry_charts.ui.server import create_app

    import uvicorn

    if open_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(package_path), host=host, port=port)
    return 0


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
