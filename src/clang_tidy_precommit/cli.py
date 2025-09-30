import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

DEFAULT_SOURCE_EXTS = (".c", ".cc", ".cpp", ".cxx", ".m", ".mm")
HEADER_EXTS = (".h", ".hh", ".hpp", ".hxx", ".ipp", ".ixx")

def debug(msg: str) -> None:
    if os.environ.get("CTP_DEBUG"):
        print(f"[clang-tidy-precommit] {msg}", file=sys.stderr)

def which_clang_tidy() -> str:
    # Allow override via env var
    override = os.environ.get("CLANG_TIDY")
    if override:
        return override
    exe = shutil.which("clang-tidy")
    if exe:
        return exe
    # Fallback: some installations may expose a module — try python -m clang_tidy if present
    try:
        import importlib.util  # noqa
        # If module exists, run it as a module
        return sys.executable + " -m clang_tidy"
    except Exception:
        pass
    return "clang-tidy"  # last resort, will likely fail with a nice message

def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="clang-tidy-precommit",
        description="Run clang-tidy on staged files using a configurable CMake-generated compile_commands.json.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    g_cmake = p.add_argument_group("CMake / compilation database")
    g_cmake.add_argument("--build-dir", "-B", default="build",
                         help="CMake build directory to use with -p (must contain compile_commands.json).")
    g_cmake.add_argument("--compile-commands", "-C", default=None,
                         help="Explicit path to compile_commands.json (overrides --build-dir).")
    g_cmake.add_argument("--cmake", action="append", default=[],
                         help="A shell command to (re)generate compile_commands.json (can be passed multiple times).")
    g_cmake.add_argument("--cmake-if-missing", action="store_true",
                         help="Only run --cmake commands if compile_commands.json is missing.")
    g_cmake.add_argument("--cmake-cwd", default=".",
                         help="Working directory for executing --cmake commands (defaults to repo root).")

    g_rules = p.add_argument_group("Rules / checks")
    g_rules.add_argument("--checks", default=None,
                         help="clang-tidy checks pattern (e.g. 'modernize-*,bugprone-*'). If omitted, uses .clang-tidy or clang-tidy defaults.")
    g_rules.add_argument("--header-filter", default=None,
                         help="Regex of headers to diagnose. By default, headers are ignored unless selected by a TU.")
    g_rules.add_argument("--warnings-as-errors", default=None,
                         help="Comma-separated globs to upgrade warnings to errors (e.g. '*').")

    g_behavior = p.add_argument_group("Behavior")
    g_behavior.add_argument("--include-headers", action="store_true",
                            help="Include header files passed by pre-commit (may require a proper TU in the compilation DB).")
    g_behavior.add_argument("--jobs", "-j", type=int, default=max(1, os.cpu_count() or 1),
                            help="Maximum parallel clang-tidy processes.")
    g_behavior.add_argument("--fix", action="store_true",
                            help="Enable clang-tidy fixes in-place (-fix). Pre-commit will fail the commit if changes are made.")
    g_behavior.add_argument("--format-style", default=None,
                            help="When using --fix, control formatting style (e.g. 'file' or 'llvm').")
    g_behavior.add_argument("--extra-arg", action="append", default=[],
                            help="Additional argument to append to the compiler command line, may be used multiple times (e.g. --extra-arg=-std=c++20).")
    g_behavior.add_argument("--extra-arg-before", action="append", default=[],
                            help="Additional argument to prepend to the compiler command line, may be used multiple times.")
    g_behavior.add_argument("--", dest="double_dash", nargs=argparse.REMAINDER,
                            help="Anything after -- is passed through verbatim to clang-tidy.")

    p.add_argument("files", nargs="*", help="Files from pre-commit.")
    return p.parse_args(list(argv))

def filter_files(files: Sequence[str], include_headers: bool) -> List[str]:
    kept = []
    for f in files:
        if os.path.isdir(f):
            for root, _dirs, fnames in os.walk(f):
                for name in fnames:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in DEFAULT_SOURCE_EXTS or (include_headers and ext in HEADER_EXTS):
                        kept.append(os.path.join(root, name))
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in DEFAULT_SOURCE_EXTS:
            kept.append(f)
        elif include_headers and ext in HEADER_EXTS:
            kept.append(f)
    return kept

def ensure_compile_commands(args: argparse.Namespace) -> Tuple[Path, Path]:
    # Decide build dir and compile_commands path
    root = Path(".").resolve()
    build_dir = Path(args.build_dir).resolve()
    cc_path = Path(args.compile_commands).resolve() if args.compile_commands else (build_dir / "compile_commands.json")

    # Run cmake if requested
    need_cmake = False
    if args.cmake:
        if args.cmake_if_missing:
            need_cmake = not cc_path.exists()
        else:
            need_cmake = True

    if need_cmake:
        cwd = Path(args.cmake_cwd).resolve()
        for cmd in args.cmake:
            debug(f"Running CMake command: {cmd} (cwd={cwd})")
            ret = subprocess.run(cmd, shell=True, cwd=str(cwd))
            if ret.returncode != 0:
                print(f"[clang-tidy-precommit] CMake command failed: {cmd}", file=sys.stderr)
                sys.exit(ret.returncode)

    if not cc_path.exists():
        print(f"[clang-tidy-precommit] Could not find compile_commands.json at: {cc_path}", file=sys.stderr)
        print("  Provide --compile-commands or --build-dir, or pass --cmake to generate it.", file=sys.stderr)
        sys.exit(2)

    return build_dir, cc_path

def build_base_cmd(args: argparse.Namespace, p_arg: Path) -> List[str]:
    clang_tidy = which_clang_tidy()
    cmd = [clang_tidy, f"-p={str(p_arg)}", "-quiet"]
    # TODO: add safeguards for args values if they contain spaces/quotes?
    # for example adding extra quotation marks around args.checks, etc.
    if args.checks:
        cmd.append(f"-checks={args.checks}")
    if args.header_filter:
        cmd.append(f"-header-filter={args.header_filter}")
    if args.warnings_as_errors:
        cmd.append(f"-warnings-as-errors={args.warnings_as_errors}")
    for ea in args.extra_arg_before:
        cmd.extend(["--extra-arg-before", ea])
    for ea in args.extra_arg:
        cmd.extend(["--extra-arg", ea])
    if args.fix:
        cmd.append("-fix")
        if args.format_style:
            cmd.append(f"-format-style={args.format_style}")
    # Pass-through args after -- (if provided)
    if args.double_dash:
        cmd.extend(args.double_dash)
    return cmd

def run_parallel(cmd: List[str], files: List[str], jobs: int) -> int:
    # Run clang-tidy in parallel for each file, collect outputs
    import concurrent.futures as cf
    results = []

    def one(f) -> Tuple[str, int, str]:
        full_cmd = cmd + [f]
        print(f"[clang-tidy-precommit] Running: {' '.join(full_cmd)}", file=sys.stderr)
        proc = subprocess.run(full_cmd, capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")
        return f, proc.returncode, out

    # Limit jobs to at least 1
    jobs = max(1, int(jobs or 1))
    rc = 0
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [ex.submit(one, f) for f in files]
        for fut in cf.as_completed(futures):
            f, code, output = fut.result()
            if output.strip():
                # Prefix each file's output for readability
                print(f"\n=== clang-tidy: {f} ===\n{output.rstrip()}\n")
            if code != 0:
                rc = 1
    return rc

def main(argv: Sequence[str] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    files = filter_files(args.files, include_headers=args.include_headers)
    if not files:
        debug("No relevant files to lint. Exiting 0.")
        return 0

    build_dir, cc_path = ensure_compile_commands(args)
    # For -p, pass a build directory (the parent containing compile_commands.json)
    p_arg = cc_path.parent if cc_path.exists() else build_dir

    base_cmd = build_base_cmd(args, p_arg=p_arg)
    if sys.platform == "darwin":
        base_cmd = ["xcrun"] + base_cmd
    debug(f"Base command: {' '.join(base_cmd)}")
    rc = run_parallel(base_cmd, files, args.jobs)
    if rc != 0 and args.fix:
        print("[clang-tidy-precommit] clang-tidy reported issues and applied fixes. "
              "Re-stage your changes if files were modified.", file=sys.stderr)
    return rc

if __name__ == "__main__":
    sys.exit(main())
