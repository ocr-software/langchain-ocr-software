"""LangChain loader: PDF, PNG, JPEG or TIFF files in, one Document per file out, read by the ocr-software.com API.

One file after the other, so at most one job is open at the API (rules: doku integrationen-regeln.md). Retries, size
limits and the document check live in the ocr-software package. The pipeline has no default: the user names it.
"""
import logging
import os
from typing import Iterator, List, Optional, Sequence, Union

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from ocr_software import Client, OcrError, PagesUnread

logger = logging.getLogger(__name__)
PathLike = Union[str, "os.PathLike[str]"]


class OcrSoftwareLoader(BaseLoader):
    """OcrSoftwareLoader("scan.pdf", pipeline="NAME@VERSION").load(). api_key defaults to OCR_SOFTWARE_API_KEY.
    format "md" needs a pipeline that offers Markdown (scan-vlm-ctc@2); the default "text" works everywhere."""

    def __init__(self, file_path: Union[PathLike, Sequence[PathLike]], *, pipeline: str, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, format: str = "text", timeout: int = 3600):
        if not pipeline:
            raise ValueError("pipeline is required: name@version (ocr-software --list-pipelines)")
        if format not in ("text", "md"):
            raise ValueError("format must be 'text' or 'md'")
        paths = [file_path] if isinstance(file_path, (str, os.PathLike)) else list(file_path)
        self.paths: List[str] = [os.fspath(p) for p in paths]
        self.pipeline, self.format, self.timeout = pipeline, format, timeout
        self._client = Client(api_key=api_key, base_url=base_url)

    def lazy_load(self) -> Iterator[Document]:
        """A page that failed does not stop the run: the Document then has metadata["incomplete"] with the reason."""
        for path in self.paths:
            metadata = {"source": path, "pipeline": self.pipeline}
            try:
                data = self._client.ocr(path, self.pipeline, self.format, timeout=self.timeout)
            except PagesUnread as e:
                data, metadata["incomplete"] = e.data, str(e)
            except OcrError as e:
                if e.code != "bad_input":  # key, address, service errors: the whole run is wrong, say so
                    raise
                logger.warning("skipped %s: %s", path, e)  # one unreadable file must not stop the other files
                continue
            yield Document(page_content=data.decode("utf-8"), metadata=metadata)
