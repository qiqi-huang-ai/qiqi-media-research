"""Create an isolated runtime for qiqi-media-research without touching secrets.

This entry point is intentionally standard-library only, so an agent can run
it immediately after a package has been downloaded or cloned.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parents[1]


def runtime_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def status(venv_dir: Path | None = None) -> dict[str, object]:
    target = venv_dir or ROOT / ".venv"
    return {
        "python": "ok" if sys.version_info >= (3, 11) else "requires Python 3.11+",
        "project": "ok" if (ROOT / "pyproject.toml").is_file() else "missing pyproject.toml",
        "runtime": str(runtime_python(target)) if runtime_python(target).is_file() else "not_created",
        "api_key": "configured" if os.environ.get("TIKHUB_API_KEY") else "missing",
        "secrets_written": False,
        "tikhub_calls": 0,
    }


def setup(venv_dir: Path | None = None) -> dict[str, object]:
    """Create ``.venv`` and install the package. API keys are never read back."""
    target = venv_dir or ROOT / ".venv"
    result = status(target)
    if result["python"] != "ok" or result["project"] != "ok":
        return result
    created = not runtime_python(target).is_file()
    if created:
        venv.EnvBuilder(with_pip=True).create(target)
    python = runtime_python(target)
    subprocess.run([str(python), "-m", "pip", "install", "."], cwd=ROOT, check=True)
    result.update({"runtime": str(python), "dependencies": "installed", "venv_created": created})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up an isolated qiqi-media-research runtime without configuring secrets")
    parser.add_argument("--setup", action="store_true", help="Create .venv and install this package")
    parser.add_argument("--venv", type=Path, help="Optional local virtual-environment directory")
    args = parser.parse_args()
    result = setup(args.venv) if args.setup else status(args.venv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["python"] == "ok" and result["project"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
