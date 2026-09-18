"""Local, non-billing installation diagnostics."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = ("SKILL.md", "pyproject.toml", "scripts/api_client.py", "adapters/douyin.py", "adapters/xiaohongshu.py")
REQUIRED_IMPORTS = ("scripts.api_client", "scripts.models", "adapters.douyin", "adapters.xiaohongshu")


def diagnose(output_dir: str | Path | None = None) -> dict[str, object]:
    missing_files = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    failed_imports = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except (ImportError, SyntaxError):
            failed_imports.append(name)
    target = Path(output_dir) if output_dir else ROOT / "research-output"
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target, prefix="doctor-", delete=True):
            writable = True
    except OSError:
        writable = False
    return {
        "python": "ok" if sys.version_info >= (3, 11) else "requires Python 3.11+",
        "required_files": "ok" if not missing_files else {"missing": missing_files},
        "imports": "ok" if not failed_imports else {"failed": failed_imports},
        "api_key": "configured" if os.environ.get("TIKHUB_API_KEY") else "missing",
        "output_directory": "writable" if writable else "not_writable",
        "network_calls": 0,
    }


def main() -> int:
    result = diagnose()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    required = ("python", "required_files", "imports", "output_directory")
    return 0 if all(result[key] in {"ok", "writable"} for key in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
