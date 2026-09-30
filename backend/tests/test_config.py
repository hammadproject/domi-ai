from app.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.llm_model == "gemini-3.1-flash-lite"
    assert s.embedding_dim == 768
    assert s.cors_origin_list == ["http://localhost:3000"]


def test_env_override_and_secret_masking(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    monkeypatch.setenv("EMBEDDING_DIM", "1536")
    s = Settings(_env_file=None)
    assert s.embedding_dim == 1536
    assert s.gemini_api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(s)
