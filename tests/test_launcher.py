from run import _provider_configuration_summary


def test_provider_configuration_summary_reports_availability_without_keys(
    monkeypatch,
) -> None:
    groq_key = "private-groq-key"
    gemini_key = "private-gemini-key"
    monkeypatch.setenv("GROQ_API_KEY", groq_key)
    monkeypatch.setenv("GEMINI_API_KEY", gemini_key)

    summary = _provider_configuration_summary()

    assert summary == (
        "Groq: configured",
        "Gemini fallback: configured",
    )
    assert groq_key not in " ".join(summary)
    assert gemini_key not in " ".join(summary)


def test_provider_configuration_summary_allows_missing_gemini(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "configured-groq")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert _provider_configuration_summary() == (
        "Groq: configured",
        "Gemini fallback: not configured",
    )
