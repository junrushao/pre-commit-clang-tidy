# clang-tidy-precommit-hook

A **from-scratch** pre-commit hook repo that runs [`clang-tidy`](https://clang.llvm.org/extra/clang-tidy/) against your staged C/C++ files.
It is designed for CMake-based projects and lets users:

- configure the exact CMake command(s) that generate `compile_commands.json`
- point to a specific `compile_commands.json` (or build directory) to use
- choose the set of clang-tidy checks (rules) to run

`clang-tidy` itself is installed from PyPI (via wheels) so no system LLVM install is required.

---

## Quick start

1. **Install pre-commit** (once per machine):

   ```bash
   pipx install pre-commit  # or: pip install pre-commit
   ```

2. **Add this hook to your project’s `.pre-commit-config.yaml`:**

   ```yaml
   repos:
     - repo: https://github.com/your-org/clang-tidy-precommit-hook
       rev: v0.1.0
       hooks:
         - id: clang-tidy-cmake
           # install clang-tidy binary from PyPI inside the hook venv
           additional_dependencies: [ "clang-tidy>=18,<23" ]
           args:
             # (A) generate compile_commands.json if missing
             - --cmake=cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_BUILD_TYPE=Debug
             - --cmake-if-missing
             # (B) tell clang-tidy where to find the compilation database
             - --build-dir=build          # or: --compile-commands=build/compile_commands.json
             # (C) select the rules
             - --checks=modernize-*,bugprone-*,performance-*,readability-*
             # (optional) useful extras
             - --warnings-as-errors=*
             - --extra-arg=-std=c++20
             - --jobs=8
   ```

   Then enable:

   ```bash
   pre-commit install
   ```

3. **Commit as usual.** Staged C/C++ sources are checked automatically.

> **Tip:** prefer a project-wide `.clang-tidy` file to encode rules. If `--checks` is omitted,
> clang-tidy will pick up `.clang-tidy` from your repo root and use that configuration.

---

## Local development / running manually

You can also run the hook directly without pre-commit:

```bash
pip install .
pip install "clang-tidy>=18,<23"
clang-tidy-precommit --cmake="cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON" --cmake-if-missing --build-dir build --checks "bugprone-*,modernize-*" path/to/file.cpp
```

---

## Configuration reference

- `--build-dir, -B <dir>`  
  CMake build directory used with `-p`. Must contain `compile_commands.json`.

- `--compile-commands, -C <path>`  
  Explicit path to the compilation database. Overrides `--build-dir`.

- `--cmake <cmd>` (repeatable)  
  A shell command to generate `compile_commands.json`. Use `--cmake-if-missing` to only run when absent.
  Example: `--cmake="cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_BUILD_TYPE=Debug"`

- `--cmake-cwd <dir>`  
  Working directory for the `--cmake` commands (defaults to repo root).

- `--checks "<patterns>"`  
  Checks to run (comma-separated globs). If omitted, clang-tidy reads from `.clang-tidy` or uses defaults.

- `--header-filter <regex>`  
  A regex that restricts which headers to diagnose.

- `--warnings-as-errors "<globs>"`  
  Promote matching warnings to errors (e.g. `*`).

- `--include-headers`  
  Include header files when running the hook. By default, only source files are analyzed because headers
  sometimes require a translation unit in the compile DB.

- `--jobs, -j <n>`  
  Maximum number of parallel clang-tidy processes (default: CPU count).

- `--fix`  
  Apply available fixes in-place. If files change, the commit will fail and you must re-stage them.

- `--format-style <style>`  
  When using `--fix`, control formatting application (e.g. `file`, `llvm`).

- `--extra-arg`, `--extra-arg-before` (repeatable)  
  Extra compiler flags for clang-tidy’s internal compiler invocation, e.g. `--extra-arg=-stdlib=libc++`.

- `-- <args...>`  
  Pass-through anything after `--` directly to `clang-tidy`.

---

## Example `.clang-tidy`

Put this in your repository root to centrally manage rules:

```yaml
Checks: >
  bugprone-*,
  modernize-*,
  performance-*,
  readability-*
WarningsAsErrors: '*'
HeaderFilterRegex: '.*'
FormatStyle: file
```

---

## Notes & compatibility

- This hook relies on the `clang-tidy` **wheels from PyPI** (installed via `additional_dependencies`).  
  See the package: https://pypi.org/project/clang-tidy/

- `-p` should point to the **build directory** that contains `compile_commands.json`.

- For CMake, remember to enable the compilation database export:

  ```bash
  cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
  ```

- On header files: clang-tidy works best when run on translation units. Use `--include-headers`
  if your DB includes headers or you want them inspected anyway.

---

## License

MIT
