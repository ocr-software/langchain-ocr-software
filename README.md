# langchain-ocr-software: read PDFs and scans in LangChain

A LangChain document loader that sends PDF, PNG, JPEG or TIFF files to the [ocr-software.com OCR API](https://ocr-software.com/) and returns one `Document` per page. The files leave your machine for the API (Helsinki, EU), or for your own server if you set `base_url`.

```
pip install git+https://github.com/ocr-software/langchain-ocr-software
# not on PyPI yet; after the first release: pip install langchain-ocr-software
# the client ocr-software comes from PyPI by itself
export OCR_SOFTWARE_API_KEY=ocr_...        # get a key at https://ocr-software.com/order/
```

```python
from langchain_ocr_software import OcrSoftwareLoader

loader = OcrSoftwareLoader("scan.pdf")      # no pipeline given: the cheapest available one, named in the log and in metadata
docs = loader.load()                        # or loader.lazy_load()
print(docs[0].page_content, docs[0].metadata)   # metadata: source, pipeline, page (1-based)
```

- `file_path`: one path or a list of paths.
- `pipeline`: optional, `name@version`. Without it the cheapest available pipeline is used and logged (same rule as the `ocr-software` command). The list: `ocr-software --list-pipelines`.
- `format`: `"text"` (default) or `"md"`; Markdown works with `scan-ctc@2` too (only `## Page N` headings) and with `scan-vlm-ctc@2` (headings, tables, more layout).
- `split_pages`: `True` (default) gives one `Document` per page with `metadata["page"]`, counted from 1, so a RAG answer can cite "page 4". `False` gives one `Document` per file. The text result separates pages with a form feed (`\f`), the Markdown result starts each page with `## Page N`; the loader splits at exactly these marks.
- `api_key`: default from `OCR_SOFTWARE_API_KEY`. `base_url`: default `https://api.ocr-software.com`; for your own server e.g. `http://127.0.0.1:8080`.
- Files are read one after the other, so at most one job is open at the API. A page that failed does not stop the run; the `Document` then has `metadata["incomplete"]` with the reason. A file that is missing, empty or not a PDF, PNG, JPEG or TIFF is skipped with a log warning, unless `on_error="raise"` is set, which stops at the first such file with an `OcrError`. If every file was skipped, the run raises `OcrError` instead of returning an empty list. A wrong key or address always stops the run; import `OcrError` from `langchain_ocr_software`.
- Wrong API keys: after several wrong keys from one address the service answers `429 locked_out` with `Retry-After` for wrong keys from that address (a correct key still works, also from the same office network). Do not retry in a loop; fix the key.

Tests (fake local service, no network, no key): `pip install -e ".[test]"` and `python -m pytest -p no:cacheprovider .`

MIT, see `LICENSE`. Operated by Helm & Nagel GmbH. [Terms](https://ocr-software.com/legal/saas-terms/) · [Privacy](https://ocr-software.com/legal/privacy/) · [Imprint](https://ocr-software.com/legal/imprint/) · [Security](https://ocr-software.com/legal/security/)
