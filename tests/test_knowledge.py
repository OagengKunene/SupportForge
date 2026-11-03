import pytest

from supportforge.knowledge import KnowledgeBase


def test_retrieval_returns_stable_evidence(knowledge, settings):
    result = knowledge.search("duplicate settled charges invoice")
    assert result[0].document == "billing.md"
    assert "settled" in result[0].excerpt
    assert result[0].id.startswith("kb-")
    knowledge.ingest(settings.knowledge_dir)
    assert knowledge.search("duplicate settled charges invoice")[0].id == result[0].id


def test_empty_and_unmatched_searches(knowledge):
    assert knowledge.search("the and please") == []
    assert knowledge.search("quantum teleportation") == []


def test_search_handles_fts_and_sql_metacharacters(knowledge, store):
    sources = knowledge.search("refund\" OR '; DROP TABLE runs; --")
    assert any(source.document == "refunds.md" for source in sources)
    assert store.stats()["runs"] == 0


def test_reindex_is_not_additive(knowledge, settings, store):
    count = store.stats()["knowledge_chunks"]
    assert knowledge.ingest(settings.knowledge_dir) == count
    assert store.stats()["knowledge_chunks"] == count
    assert len(knowledge.documents()) == 5


def test_limits_and_missing_knowledge(knowledge, tmp_path):
    assert len(knowledge.search("account password invoice refund API", limit=999)) <= 6
    with pytest.raises(ValueError, match="does not exist"):
        knowledge.ingest(tmp_path / "absent")
    with pytest.raises(ValueError, match="non-empty"):
        knowledge.ingest(tmp_path)


def test_chunking_long_plain_markdown(store, tmp_path):
    (tmp_path / "guide.md").write_text("Long policy. " * 200)
    base = KnowledgeBase(store)
    assert base.ingest(tmp_path) == 2
    assert len(base.search("policy")) == 2
