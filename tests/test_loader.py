from pathlib import Path

import pytest

from langchain_ocr_software import OcrError, OcrSoftwareLoader


def make(fake, files, **kw):
    return OcrSoftwareLoader(files, pipeline="p@1", base_url=fake.url, **kw)


def test_one_document_per_file_with_source_and_page_in_metadata(fake, docs):
    out = make(fake, docs[:2]).load()
    assert [d.page_content for d in out] == ["text of j1", "text of j2"]
    assert out[0].metadata == {"source": docs[0], "pipeline": "p@1", "page": 1}


def test_single_path_and_pathlike(fake, docs):
    assert make(fake, Path(docs[0])).load()[0].page_content == "text of j1"


def test_lazy_load_reads_nothing_until_asked(fake, docs):
    it = make(fake, docs).lazy_load()
    assert fake.log == []
    next(it)
    assert fake.state["jobs"] == 1


def test_files_go_one_after_the_other_never_two_jobs_open(fake, docs):
    make(fake, docs).load()
    calls = [(m, p) for m, p, _, _ in fake.log]
    submits = [i for i, c in enumerate(calls) if c == ("POST", "/v1/jobs")]
    assert len(submits) == 3
    for n, (first, second) in enumerate(zip(submits, submits[1:]), 1):
        assert ("GET", "/v1/jobs/j%d/result" % n) in calls[first:second]


def test_busy_503_is_retried_with_one_idempotency_key(fake, docs):
    fake.state["fail_submits"] = 2
    out = make(fake, docs[:1]).load()
    keys = {k for m, p, _, k in fake.log if m == "POST"}
    assert out[0].page_content == "text of j1" and len(keys) == 1 and None not in keys and fake.state["jobs"] == 1


def test_unread_page_is_flagged_not_hidden(fake, docs):
    fake.state["unread"] = True
    doc = make(fake, docs[:1]).load()[0]
    assert doc.page_content == "text of j1" and "1 page(s) failed" in doc.metadata["incomplete"]


def test_key_from_environment_or_argument_goes_in_the_header_only(fake, docs):
    make(fake, docs[:1]).load()
    make(fake, docs[:1], api_key="ocr_other").load()
    assert {a for _, _, a, _ in fake.log if a} == {"Bearer ocr_testkey", "Bearer ocr_other"}


def test_bad_format_and_missing_file_fail_clearly(fake, tmp_path):
    with pytest.raises(ValueError):
        make(fake, [], format="pdf")
    with pytest.raises(ValueError, match="on_error"):
        make(fake, [], on_error="ignore")
    assert fake.log == []


def test_one_bad_file_is_skipped_with_a_warning_the_others_are_read(fake, docs, tmp_path, caplog):
    """Review 13.11.2026: an unreadable file in the list stopped the run and dropped the files already read."""
    empty = tmp_path / "leer.pdf"
    empty.write_bytes(b"")
    with caplog.at_level("WARNING"):
        out = make(fake, [docs[0], str(empty), str(tmp_path / "nope.pdf"), docs[1]]).load()
    assert [d.page_content for d in out] == ["text of j1", "text of j2"]
    assert "file is empty" in caplog.text and "not a file" in caplog.text


THREE_PAGES = b"one\n\ftwo\n\fthree\n"


def test_one_document_per_page_with_page_number_from_1(fake, docs):
    """Kundentest 13.11.2026 (Fund 2): a RAG citation 'page 4' needs metadata["page"]."""
    fake.state["result"] = THREE_PAGES
    out = make(fake, docs[:1]).load()
    assert [(d.page_content, d.metadata["page"], d.metadata["source"]) for d in out] == [("one\n", 1, docs[0]), ("two\n", 2, docs[0]), ("three\n", 3, docs[0])]


def test_markdown_pages_and_the_switch_for_one_document_per_file(fake, docs):
    fake.state["result"] = b"## Page 1\n\nalpha\n\n## Page 2\n\nbeta\n"
    out = make(fake, docs[:1], format="md").load()
    assert [(d.page_content, d.metadata["page"]) for d in out] == [("alpha\n", 1), ("beta\n", 2)]
    whole = make(fake, docs[:1], format="md", split_pages=False).load()
    assert len(whole) == 1 and "page" not in whole[0].metadata and whole[0].page_content.startswith("## Page 1")


def test_an_unread_page_marks_every_page_document_of_the_file(fake, docs):
    fake.state["result"], fake.state["unread"] = THREE_PAGES, True
    out = make(fake, docs[:1]).load()
    assert len(out) == 3 and all("1 page(s) failed" in d.metadata["incomplete"] for d in out)


def test_no_pipeline_uses_the_cheapest_and_says_so(fake, docs, caplog):
    """Kundentest 13.11.2026 (Fund 4): pipeline optional, default as in the Python client; the choice is in metadata and log."""
    with caplog.at_level("INFO"):
        out = OcrSoftwareLoader(docs[:2], base_url=fake.url).load()
    assert {d.metadata["pipeline"] for d in out} == {"cheap@1"} and "using cheap@1" in caplog.text
    assert any(q.startswith("pipeline=cheap@1") for q in fake.queries)


def test_on_error_raise_stops_at_the_first_bad_file(fake, docs, tmp_path):
    with pytest.raises(OcrError, match="not a file"):
        make(fake, [docs[0], str(tmp_path / "nope.pdf"), docs[1]], on_error="raise").load()
    assert fake.state["jobs"] == 1


def test_only_bad_files_is_an_error_not_an_empty_list(fake, tmp_path):
    """Kundentest 13.11.2026 (Fund 3): a typo in the only path gave [] and no error."""
    with pytest.raises(OcrError, match="none of the 2 files could be read.*nope.pdf") as e:
        make(fake, [str(tmp_path / "nope.pdf"), str(tmp_path / "x.pdf")]).load()
    assert e.value.code == "bad_input"
    assert make(fake, []).load() == []


def test_ocr_error_can_be_imported_from_the_package():
    import langchain_ocr_software
    import ocr_software
    assert langchain_ocr_software.OcrError is ocr_software.OcrError
