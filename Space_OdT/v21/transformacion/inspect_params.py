from __future__ import annotations

import argparse
import ast
import logging
import time
from pathlib import Path
from typing import Iterable, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger: logging.Logger = logging.getLogger(__name__)


EXCLUDED_DIR_NAMES: set[str] = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "build",
    "dist",
}


def iter_py_files(root_dir: Path) -> Iterable[Path]:
    # Walk repository and yield *.py files excluding common noise folders.
    for path in root_dir.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def extract_function_param_names(function_node: ast.AST) -> list[str]:
    # Extract *real* parameter names including keyword-only, excluding markers like "*".
    if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    args_obj: ast.arguments = function_node.args

    posonly_names: list[str] = [a.arg for a in getattr(args_obj, "posonlyargs", [])]
    positional_names: list[str] = [a.arg for a in args_obj.args]
    kwonly_names: list[str] = [a.arg for a in args_obj.kwonlyargs]

    vararg_name: list[str] = [args_obj.vararg.arg] if args_obj.vararg is not None else []
    kwarg_name: list[str] = [args_obj.kwarg.arg] if args_obj.kwarg is not None else []

    all_names: list[str] = posonly_names + positional_names + vararg_name + kwonly_names + kwarg_name

    # Exclude common implicit receiver names.
    filtered: list[str] = [n for n in all_names if n not in {"self", "cls"}]
    return filtered


def collect_unique_param_names(
    root_dir: Path,
    *,
    exclude_function_names: set[str],
) -> set[str]:
    # Cache all parameter names in a set, no duplicates.
    unique_param_names: set[str] = set()

    for py_file in iter_py_files(root_dir):
        try:
            source_text: str = py_file.read_text(encoding="utf-8")
        except Exception:
            logger.exception("read_failed file=%s", str(py_file))
            continue

        try:
            tree: ast.AST = ast.parse(source_text, filename=str(py_file))
        except SyntaxError as exc:
            logger.warning(
                "parse_syntax_error file=%s line=%s msg=%s",
                str(py_file),
                getattr(exc, "lineno", None),
                str(exc),
            )
            continue
        except Exception:
            logger.exception("parse_failed file=%s", str(py_file))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name: str = node.name
                if func_name in exclude_function_names:
                    continue

                param_names: list[str] = extract_function_param_names(node)
                unique_param_names.update(param_names)

    return unique_param_names


def write_bullets(output_path: Path, items: list[str]) -> None:
    # Write bullet list to file.
    content: str = "\n".join(f"- {name}" for name in items) + ("\n" if items else "")
    try:
        output_path.write_text(content, encoding="utf-8")
    except Exception:
        logger.exception("write_failed file=%s", str(output_path))
        raise


def main() -> int:
    start_time_s: float = time.perf_counter()

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="inspect_params_to_needs_log",
        description="Collect unique Python function parameter names and write them as bullets to needs.log",
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory to scan")
    parser.add_argument("--out", type=str, default="needs.log", help="Output log file")
    args: argparse.Namespace = parser.parse_args()

    root_dir: Path = Path(args.root).resolve()
    output_path: Path = Path(args.out).resolve()

    logger.info("scan_start root_dir=%s out=%s", str(root_dir), str(output_path))

    exclude_function_names: set[str] = {"main"}  # exclude main() explicitly
    unique_param_names: set[str] = collect_unique_param_names(
        root_dir,
        exclude_function_names=exclude_function_names,
    )

    sorted_names: list[str] = sorted(unique_param_names, key=str.casefold)

    # Print bullet list to screen.
    for name in sorted_names:
        print(f"- {name}")

    # Write bullet list to needs.log.
    write_bullets(output_path, sorted_names)

    elapsed_s: float = time.perf_counter() - start_time_s
    logger.info("scan_done unique_count=%d elapsed_s=%.6f", len(sorted_names), elapsed_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

