"""LangChain document loader for the ocr-software.com OCR API."""
from ocr_software import OcrError

from .loader import OcrSoftwareLoader

__version__ = "0.1.0"
__all__ = ["OcrSoftwareLoader", "OcrError", "__version__"]
