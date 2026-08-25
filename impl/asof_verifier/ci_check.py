#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ci_check.py — mechanical enforcement of the anti-certification-loop red line
(C5 Requirement 5.8(4) / §6.4): the independent verifier and the compiler must
share ZERO project-internal modules.

Assertions (exit 0 iff all hold):
  A1  every import in impl/asof_verifier/**.py resolves to the whitelist
      (python stdlib ∪ {duckdb}) or to a module inside asof_verifier itself;
  A2  no verifier file imports (or path-hacks toward) any compiler location:
      impl/asof_compiler/**  and  pilot/domains/*/compiler.py, pilot/public/**;
  A3  the project-internal import-root sets of the two sides are DISJOINT
      (empty intersection), stdlib/duckdb whitelisted out;
  A4  no verifier file uses dynamic-import escape hatches aimed at the
      compiler (importlib/__import__ with a literal containing 'compiler',
      or sys.path manipulation mentioning a compiler directory).

The compiler side (impl/asof_compiler) may not exist yet (it is built by a
separate stage); its absence is reported and A3 degrades to checking the
verifier side only — the check stays green and must be re-run once the
compiler lands (it is cheap and deterministic).
"""
from __future__ import annotations

import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL = os.path.dirname(HERE)                      # .../impl
ROOT = os.path.dirname(IMPL)                      # project root
VERIFIER_DIR = HERE
COMPILER_DIRS = [
    os.path.join(IMPL, "asof_compiler"),
    os.path.join(ROOT, "pilot", "domains"),
    os.path.join(ROOT, "pilot", "public"),
]

# stdlib whitelist: python 3.10+ exposes sys.stdlib_module_names; on older
# interpreters fall back to a curated set covering everything a pure
# stdlib+duckdb implementation may plausibly touch.
_FALLBACK_STDLIB = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "bisect", "builtins",
    "calendar", "cmath", "collections", "concurrent", "configparser", "contextlib",
    "copy", "csv", "ctypes", "dataclasses", "datetime", "decimal", "difflib",
    "enum", "errno", "fractions", "functools", "gc", "getopt", "getpass", "glob",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "importlib", "inspect",
    "io", "itertools", "json", "keyword", "logging", "lzma", "math", "mimetypes",
    "multiprocessing", "numbers", "operator", "os", "pathlib", "pickle", "platform",
    "pprint", "queue", "random", "re", "secrets", "select", "shlex", "shutil",
    "signal", "socket", "sqlite3", "stat", "statistics", "string", "struct",
    "subprocess", "sys", "tempfile", "textwrap", "threading", "time", "timeit",
    "token", "tokenize", "traceback", "types", "typing", "unicodedata", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile", "zlib", "__future__",
}
STDLIB = set(getattr(sys, "stdlib_module_names", _FALLBACK_STDLIB))
WHITELIST = STDLIB | {"duckdb"}

_SYSPATH_FUNCS = {"sys.path.insert", "sys.path.append", "sys.path.extend"}
_DYNIMPORT_FUNCS = {"__import__", "importlib.import_module", "import_module"}


def py_files(root):
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in
                       ("__pycache__", ".git", "forge_out")]
        for fn in filenames:
            # skip macOS AppleDouble resource forks ("._x.py"): not python source
            if fn.endswith(".py") and not fn.startswith("._"):
                out.append(os.path.join(dirpath, fn))
    return out


def _dotted(node):
    """Best-effort dotted name of a call target (AST-based, no regex)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _call_string_constants(call):
    out = []
    for sub in ast.walk(call):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def import_roots(path):
    """Top-level dotted roots of all static imports in a file, plus dynamic
    import literals and sys.path-manipulation string constants (for A2/A4).
    Fully AST-based — message strings and docstrings cannot false-positive."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=path)
    roots = set()
    dyn = []
    syspath_lits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                roots.add(".")  # relative import: stays inside its own package
            elif node.module:
                roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name in _DYNIMPORT_FUNCS:
                dyn.extend(_call_string_constants(node))
            elif name in _SYSPATH_FUNCS:
                syspath_lits.extend(_call_string_constants(node))
    return roots, dyn, syspath_lits


def side_summary(files, own_module_names):
    agg = {"files": {}, "roots": set(), "internal": set(), "dyn": {}, "syspath": {},
           "unparsed": []}
    for f in files:
        try:
            roots, dyn, sp = import_roots(f)
        except SyntaxError as e:
            agg["unparsed"].append("%s: %s" % (f, e))
            continue
        agg["files"][f] = sorted(roots)
        agg["roots"] |= roots
        if dyn:
            agg["dyn"][f] = dyn
        if sp:
            agg["syspath"][f] = sp
    agg["internal"] = {r for r in agg["roots"]
                       if r not in WHITELIST and r != "." and r not in own_module_names}
    return agg


def main():
    failures = []
    notes = []

    v_files = py_files(VERIFIER_DIR)
    v_own = {os.path.splitext(os.path.basename(f))[0] for f in v_files}
    v = side_summary(v_files, set())

    c_files = []
    for d in COMPILER_DIRS:
        c_files += py_files(d)
    compiler_present = os.path.isdir(COMPILER_DIRS[0])
    if not compiler_present:
        notes.append("impl/asof_compiler absent (not yet built): A3 degrades to the "
                     "verifier-side assertions; re-run once the compiler lands")
    c_own = {os.path.splitext(os.path.basename(f))[0] for f in c_files}
    c = side_summary(c_files, set())

    # A1: verifier imports ⊆ whitelist ∪ intra-verifier modules
    for f, roots in sorted(v["files"].items()):
        bad = [r for r in roots
               if r not in WHITELIST and r != "." and r not in v_own]
        if bad:
            failures.append("A1: %s imports outside stdlib∪{duckdb}∪verifier: %s"
                            % (os.path.relpath(f, ROOT), ", ".join(sorted(bad))))

    # A2: verifier must not import any compiler module name, nor reference
    #     compiler paths in dynamic imports / sys.path hacks
    compiler_module_names = (c_own | {"asof_compiler", "compiler",
                                      "compile_question", "verify"})
    compiler_module_names -= {"__init__"}
    for f, roots in sorted(v["files"].items()):
        hit = [r for r in roots if r in ("asof_compiler", "compiler")]
        if hit:
            failures.append("A2: %s imports compiler module(s): %s"
                            % (os.path.relpath(f, ROOT), ", ".join(hit)))
    for f, lits in sorted(v["dyn"].items()):
        hit = [x for x in lits if "compiler" in x]
        if hit:
            failures.append("A2: %s dynamically imports %s"
                            % (os.path.relpath(f, ROOT), ", ".join(hit)))
    for f, lits in sorted(v["syspath"].items()):
        hit = [x for x in lits if "compiler" in x or "pilot" in x]
        if hit:
            failures.append("A2: %s manipulates sys.path toward a compiler dir: %s"
                            % (os.path.relpath(f, ROOT), " | ".join(hit)))

    # A3: project-internal import roots of the two sides must be disjoint;
    #     additionally neither side may import a module whose NAME belongs to
    #     the other side (shared-module exclusion).
    inter = v["internal"] & c["internal"]
    if inter:
        failures.append("A3: shared project-internal import roots: %s"
                        % ", ".join(sorted(inter)))
    cross_v = {r for r in v["roots"] if r in c_own and r not in WHITELIST}
    if cross_v:
        failures.append("A3: verifier imports module name(s) owned by the compiler "
                        "side: %s" % ", ".join(sorted(cross_v)))
    cross_c = {r for r in c["roots"] if r in v_own and r not in WHITELIST}
    if cross_c:
        failures.append("A3: compiler side imports verifier module name(s): %s"
                        % ", ".join(sorted(cross_c)))

    report = {
        "ok": not failures,
        "verifier_files": [os.path.relpath(f, ROOT) for f in v_files],
        "verifier_import_roots": sorted(v["roots"]),
        "compiler_files": [os.path.relpath(f, ROOT) for f in c_files],
        "compiler_import_roots": sorted(c["roots"]),
        "compiler_side_present": compiler_present,
        "shared_internal_roots": sorted(v["internal"] & c["internal"]),
        "whitelist": "stdlib ∪ {duckdb}",
        "failures": failures,
        "notes": notes,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        print("\nCI-CHECK: FAIL (%d assertion(s) violated)" % len(failures),
              file=sys.stderr)
        return 1
    print("\nCI-CHECK: PASS — import graphs disjoint "
          "(verifier ⊨ stdlib+duckdb only; zero compiler imports)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
