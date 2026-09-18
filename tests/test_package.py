from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_required_project_files_exist():
    required = [
        "SKILL.md",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
    ]
    assert all((ROOT / name).is_file() for name in required)


def test_forbidden_release_artifacts_are_absent():
    forbidden = {".DS_Store", "__pycache__"}
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any(
        Path(name).name in forbidden
        or "__pycache__" in Path(name).parts
        or Path(name).suffix == ".pyc"
        for name in tracked
    )


def test_skill_declares_exact_research_modes():
    text = (ROOT / "SKILL.md").read_text()
    modes = {
        "niche-discovery", "trend-scan", "competitor-discovery",
        "account-audit", "viral-breakdown", "comment-mining",
        "content-gap", "cross-platform", "brand-product",
        "idea-generation", "market-map",
    }
    assert all(mode in text for mode in modes)
    assert "TIKHUB_API_KEY" in text
    assert "MCP" not in text


def test_skill_does_not_claim_unverified_platforms():
    text = (ROOT / "SKILL.md").read_text()
    assert "已验证：抖音、小红书" in text
