import pytest


@pytest.fixture(autouse=True)
def isolate_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep automated tests independent from local provider credentials."""
    for variable in (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(variable, raising=False)
