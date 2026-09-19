from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _release_files():
    if (ROOT / ".git").exists():
        names = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        return [Path(name) for name in names]
    ignored = {".pytest_cache", "__pycache__", ".venv", "research-output", "tmp"}
    return [path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file() and not ignored.intersection(path.relative_to(ROOT).parts)]


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
    tracked = _release_files()
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


def test_agent_bridges_point_to_root_skill_without_copying_it():
    root_skill = (ROOT / "SKILL.md").read_text()
    bridges = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / ".cursor/rules/qiqi-media-research.mdc",
        ROOT / "workbuddy/SKILL.md",
    ]
    for bridge in bridges:
        if not bridge.exists():
            continue
        text = bridge.read_text()
        assert "SKILL.md" in text
        assert len(text) < len(root_skill) * 0.35


def test_tracked_release_files_have_no_machine_paths_or_reference_package_names():
    tracked = _release_files()
    forbidden_names = ("konglong" + "-research", "douyin" + "-extractor", "TikHub " + "MCP")
    for name in tracked:
        path = ROOT / name
        if not path.is_file() or path.suffix in {".png", ".jpg", ".zip"}:
            continue
        text = path.read_text(errors="ignore")
        assert "/Users" + "/" not in text
        assert not any(term in text for term in forbidden_names)
        tokens = re.findall(r"Bearer\s+([^\s\"']+)", text)
        assert all(token.startswith(("$", "{", "secret-value", "example")) for token in tokens)
