"""LangChain loader: PDF, PNG, JPEG or TIFF files in, one Document per page out, read by the ocr-software.com API.

One file after the other, so at most one job is open at the API (rules: doku integrationen-regeln.md). Retries, size
limits and the document check live in the ocr-software package. Without a pipeline the default is used: the fastest
and cheapest available one (ocr_software.advice.default_pipeline), named in the log.
"""
import logging
import os
from typing import Iterator, List, Optional, Sequence, Union

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from ocr_software import Client, OcrError, PagesUnread, split_pages

logger = logging.getLogger(__name__)
PathLike = Union[str, "os.PathLike[str]"]


class OcrSoftwareLoader(BaseLoader):
    """OcrSoftwareLoader("scan.pdf").load(). api_key defaults to OCR_SOFTWARE_API_KEY. pipeline: "name@version"
    (ocr-software --list-pipelines), default the fastest and cheapest. Each Document is one page, metadata["page"] counts
    from 1; split_pages=False gives one Document per file (pages separated by a form feed in "text", by "## Page N"
    headings in "md"). format "md" works with every pipeline; real headings and lists need scan-vlm-ctc@2. on_error
    "skip" (default) skips a file that is missing, empty or not a PDF/PNG/JPEG/TIFF with a log warning, "raise" raises."""

    def __init__(self, file_path: Union[PathLike, Sequence[PathLike]], *, pipeline: Optional[str] = None,
                 api_key: Optional[str] = None, base_url: Optional[str] = None, format: str = "text", timeout: int = 3600,
                 split_pages: bool = True, on_error: str = "skip"):
        if format not in ("text", "md"):
            raise ValueError("format must be 'text' or 'md'")
        if on_error not in ("skip", "raise"):
            raise ValueError("on_error must be 'skip' or 'raise'")
        paths = [file_path] if isinstance(file_path, (str, os.PathLike)) else list(file_path)
        self.paths: List[str] = [os.fspath(p) for p in paths]
        self.pipeline, self.format, self.timeout = pipeline, format, timeout
        self.split_pages, self.on_error = split_pages, on_error
        self._client = Client(api_key=api_key, base_url=base_url)

    def lazy_load(self) -> Iterator[Document]:
        """A page that failed does not stop the run: the Documents of that file carry metadata["incomplete"] with the
        reason. Other errors (key, address, service) are raised. If not one file could be read, that is an error."""
        pipeline = self.pipeline or self._client.default_pipeline()
        if not self.pipeline:
            logger.info("no pipeline given, using %s (the fastest and cheapest available)", pipeline)
        skipped, read = [], 0
        for path in self.paths:
            metadata = {"source": path, "pipeline": pipeline}
            try:
                data = self._client.ocr(path, pipeline, self.format, timeout=self.timeout)
            except PagesUnread as e:
                data, metadata["incomplete"] = e.data, str(e)
            except OcrError as e:
                if e.code != "bad_input" or self.on_error == "raise":  # key, address, service errors: the whole run is wrong, say so
                    raise
                logger.warning("skipped %s: %s", path, e)  # one unreadable file must not stop the other files
                skipped.append(str(e))
                continue
            text = data.decode("utf-8")
            read += 1
            for number, content in split_pages(text, self.format) if self.split_pages else [(None, text)]:
                yield Document(page_content=content, metadata=dict(metadata, page=number) if number else dict(metadata))
        if skipped and not read:
            raise OcrError("none of the %d files could be read, first problem: %s" % (len(skipped), skipped[0]), "bad_input")
