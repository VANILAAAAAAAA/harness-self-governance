#!/usr/bin/env python3
"""Lightweight package build readiness check.

Checks pyproject build-system metadata and tries `python -m build` only when the
optional build module is already installed. This avoids adding heavy runtime
or test dependencies to the project.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check package build backend and optional build execution")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    pyproject = root / "pyproject.toml"
    result = {"ok": False, "root": "${REPO_ROOT}", "pyproject": "pyproject.toml", "checks": [], "build_attempted": False}
    if not pyproject.exists():
        result["checks"].append({"ok": False, "name": "pyproject_exists", "message": "pyproject.toml missing"})
    else:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        build_system = data.get("build-system", {})
        backend = build_system.get("build-backend")
        requires = build_system.get("requires", [])
        result["build_backend"] = backend
        result["build_requires"] = requires
        result["checks"].append({"ok": backend == "hatchling.build", "name": "build_backend", "message": str(backend)})
        result["checks"].append({"ok": "hatchling" in requires, "name": "build_requires_hatchling", "message": str(requires)})
        result["checks"].append({"ok": (root / "src" / "graph_harness_maintain" / "__init__.py").exists(), "name": "package_init", "message": "src/graph_harness_maintain/__init__.py"})
    if importlib.util.find_spec("build") is None:
        result["checks"].append({"ok": True, "name": "python_build_module", "message": "python -m build not attempted: optional 'build' module is not installed; install with `python -m pip install build` to build distributions"})
    else:
        result["build_attempted"] = True
        proc = subprocess.run([sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(root / "artifacts" / "build_check_dist")], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        result["checks"].append({"ok": proc.returncode == 0, "name": "python_m_build", "message": proc.stdout[-4000:]})
    result["ok"] = all(check["ok"] for check in result["checks"])
    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
