"""Knowledge retrieval tests: parsing, search quality, payload citations."""

from SweetAstro.src.knowledge.retrieval import (
    KNOWLEDGE_FILES, TOPIC_CATEGORY_MAP, get_knowledge_index,
    reference_lines, retrieve_references,
)


def test_index_parses_the_curated_corpus():
    index = get_knowledge_index()
    assert len(index.entries) > 300
    files = {e.source_file for e in index.entries}
    assert files <= set(KNOWLEDGE_FILES)
    for entry in index.entries:
        assert entry.entry_id > 0
        assert entry.title
        assert entry.status in ("canon", "known", "tech", "verify")
        assert entry.tier.startswith("T")


def test_search_finds_expected_sources_for_classical_topics():
    jaimini = retrieve_references("chara dasha timing and karakas", topic="marriage")
    titles = " | ".join(e.title.lower() for e in jaimini)
    assert "jaimini" in titles or "chara" in titles

    muhurta = retrieve_references("auspicious wedding date muhurta", topic="general")
    assert any("muhurta" in e.title.lower() or "nirnaya" in e.title.lower()
               or "muhurta" in " ".join(e.categories).lower() for e in muhurta)


def test_search_is_deterministic_and_bounded():
    first = retrieve_references("wealth and career timing", topic="wealth", limit=5)
    second = retrieve_references("wealth and career timing", topic="wealth", limit=5)
    assert [e.entry_id for e in first] == [e.entry_id for e in second]
    assert len(first) <= 5
    assert all(e.entry_id > 0 for e in first)


def test_topic_map_categories_are_used():
    assert "health" in TOPIC_CATEGORY_MAP["health"]
    health = retrieve_references("recurring health issue", topic="health", limit=6)
    joined = " ".join(" ".join(e.categories).lower() for e in health)
    assert "health" in joined or "stability" in joined or "longevity" in joined


def test_reference_lines_include_source_and_status():
    entries = retrieve_references("dasha timing", topic="marriage", limit=3)
    lines = reference_lines(entries)
    assert len(lines) == len(entries)
    for line in lines:
        assert line.startswith("- ")
        assert ".md]" in line
        assert any(f"({s}" in line for s in ("canon", "known", "tech", "verify"))


def test_chat_payload_includes_source_references(monkeypatch):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    class _FakeClient:
        def complete_json(self, messages, **kwargs):
            return {
                "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
                "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
                "question": "When will I get married?", "topic": "marriage",
            }

        def stream(self, messages, **kwargs):
            for word in "ok".split(" "):
                yield {"type": "content", "text": word}

    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock)."),
    )
    client = _FakeClient()
    orch = ChatOrchestrator(client=client, store=SessionStore())
    list(orch.handle_message("src1", "When will I get married? Born 15 May 1995 14:30 in Jaipur."))

    session = orch.store.get("src1")
    assert session is not None and session.last_result is not None
    payload = orch._build_chart_payload(session, session.last_result)
    assert "Source references" in payload
    assert "never invent verses" in payload
    assert ".md]" in payload
