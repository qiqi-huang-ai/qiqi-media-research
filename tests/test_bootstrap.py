from pathlib import Path

from scripts import bootstrap


def test_bootstrap_status_never_returns_key(monkeypatch, tmp_path):
    monkeypatch.setenv("TIKHUB_API_KEY", "secret-value")
    result = bootstrap.status(tmp_path / "isolated")

    assert result["api_key"] == "configured"
    assert "secret-value" not in str(result)
    assert result["secrets_written"] is False


def test_runtime_python_uses_the_platform_venv_layout(tmp_path):
    python = bootstrap.runtime_python(tmp_path / "runtime")

    assert python.parent.name in {"bin", "Scripts"}
    assert python.name in {"python", "python.exe"}
