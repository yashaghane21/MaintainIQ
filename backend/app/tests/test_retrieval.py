import pytest

from app.utils.text import Page, chunk_pages, clean_text, extract_pages


def test_empty_knowledge_base_returns_empty(retrieval):
    result = retrieval.retrieve("pump vibration", "pump")
    assert result.status == "empty" and result.chunks == []
    assert "no indexed documents" in result.message


def test_ingest_and_retrieve_preserves_metadata(retrieval):
    pages = [Page(1, "Bearing wear causes vibration and grinding noise in the pump."),
             Page(2, "Clean the condenser coil of the HVAC unit.")]
    count = retrieval.ingest(document_id="DOC-1", title="Pump Manual", equipment_type="pump", source="pump.pdf", pages=pages)
    assert count == 2
    result = retrieval.retrieve("pump bearing vibration grinding", "pump")
    assert result.status == "ok"
    top = result.chunks[0]
    assert (top.document_id, top.document_title, top.page_number, top.source) == ("DOC-1", "Pump Manual", 1, "pump.pdf")
    assert top.chunk_id.startswith("DOC-1:p1:")
    assert 0 < top.score <= 1


def test_retrieval_filters_by_equipment_type(retrieval):
    retrieval.ingest(document_id="DOC-H", title="HVAC", equipment_type="hvac", source="h.txt",
                     pages=[Page(None, "Pump bearing vibration grinding noise.")])
    assert retrieval.retrieve("pump bearing vibration", "pump").status == "empty"


def test_irrelevant_results_below_min_score_are_dropped(retrieval):
    retrieval.ingest(document_id="DOC-1", title="T", equipment_type="pump", source="t.txt",
                     pages=[Page(None, "Lubrication schedule for gearbox oil.")])
    retrieval.settings = retrieval.settings.model_copy(update={"retrieval_min_score": 0.99})
    result = retrieval.retrieve("refrigerant leak on rooftop", "pump")
    assert result.status == "empty" and "No sufficiently relevant" in result.message


def test_retrieval_error_is_reported_not_raised(retrieval, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("index corrupted")
    retrieval.ingest(document_id="DOC-1", title="T", equipment_type="pump", source="t.txt", pages=[Page(None, "text here")])
    monkeypatch.setattr(retrieval.embedder, "embed", boom)
    result = retrieval.retrieve("anything", "pump")
    assert result.status == "error" and "RuntimeError" in result.message


def test_reingest_is_idempotent(retrieval):
    page = [Page(None, "Some manual text about pumps.")]
    retrieval.ingest(document_id="DOC-1", title="T", equipment_type="pump", source="t.txt", pages=page)
    retrieval.ingest(document_id="DOC-1", title="T", equipment_type="pump", source="t.txt", pages=page)
    assert retrieval.chunk_count("DOC-1") == 1


def test_chunking_respects_size_and_pages():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(10))
    chunks = chunk_pages([Page(3, text)], size=400, overlap=50)
    assert len(chunks) > 1
    assert all(c.page_number == 3 for c in chunks)
    assert all(len(c.text) <= 400 + 60 for c in chunks)


def test_clean_text():
    assert clean_text("Hyphen-\nated   word\r\n\n\n\nnext\x00") == "Hyphenated word\n\nnext"


def test_extract_txt_and_reject_unsupported():
    pages = extract_pages("m.txt", b"Hello manual")
    assert pages[0].text == "Hello manual" and pages[0].page_number is None
    with pytest.raises(ValueError):
        extract_pages("m.docx", b"data")
    with pytest.raises(ValueError):
        extract_pages("m.txt", b"   \n  ")
    with pytest.raises(ValueError):
        extract_pages("m.pdf", b"not a pdf")
