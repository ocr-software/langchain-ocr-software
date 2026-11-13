from pathlib import Path

import pytest

from langchain_ocr_software import OcrSoftwareLoader


def make(fake, files, **kw):
    return OcrSoftwareLoader(files, pipeline="p@1", base_url=fake.url, **kw)


def test_one_document_per_file_with_source_in_metadata(fake, docs):
    out = make(fake, docs[:2]).load()
    assert [d.page_content for d in out] == ["text of j1", "text of j2"]
    assert out[0].metadata == {"source": docs[0], "pipeline": "p@1"}


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
    with pytest.raises(ValueError, match="pipeline is required"):
        OcrSoftwareLoader("a.pdf", pipeline="")
    assert fake.log == []


def test_one_bad_file_is_skipped_with_a_warning_the_others_are_read(fake, docs, tmp_path, caplog):
    """Review 13.11.2026: an unreadable file in the list stopped the run and dropped the files already read."""
    empty = tmp_path / "leer.pdf"
    empty.write_bytes(b"")
    with caplog.at_level("WARNING"):
        out = make(fake, [docs[0], str(empty), str(tmp_path / "nope.pdf"), docs[1]]).load()
    assert [d.page_content for d in out] == ["text of j1", "text of j2"]
    assert "file is empty" in caplog.text and "not a file" in caplog.text
