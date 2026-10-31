"""Pinecone search config contract tests."""

from core.config import Settings


def _settings(**overrides: object) -> Settings:
    base = {
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "BOT_TOKEN": "bot:test",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_pinecone_search_is_disabled_by_default() -> None:
    settings = _settings()

    assert settings.PINECONE_ENABLED is False
    assert settings.PINECONE_RERANK_ENABLED is False
    assert settings.PINECONE_INDEX_NAME == ""
    assert settings.PINECONE_NAMESPACE == "public"
    assert settings.PINECONE_MODEL == "multilingual-e5-large"
    assert settings.PINECONE_RERANK_MODEL == "bge-reranker-v2-m3"


def test_pinecone_search_flags_are_explicit_opt_in() -> None:
    settings = _settings(
        PINECONE_ENABLED=True,
        PINECONE_RERANK_ENABLED=True,
        PINECONE_INDEX_NAME="phangan-search-v1-dev",
    )

    assert settings.PINECONE_ENABLED is True
    assert settings.PINECONE_RERANK_ENABLED is True
    assert settings.PINECONE_INDEX_NAME == "phangan-search-v1-dev"
