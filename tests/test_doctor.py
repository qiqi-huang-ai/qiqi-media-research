from scripts.doctor import diagnose


def test_doctor_reports_missing_key_without_showing_value(monkeypatch):
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)
    result = diagnose()
    assert result["api_key"] == "missing"


def test_doctor_never_returns_key(monkeypatch):
    monkeypatch.setenv("TIKHUB_API_KEY", "top-secret")
    result = diagnose()
    assert result["api_key"] == "configured"
    assert "top-secret" not in repr(result)
