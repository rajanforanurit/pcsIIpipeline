from pathlib import Path
from typing import Tuple
import fitz
from app.core.logging import get_logger
from app.models.common import PDFType

logger = get_logger(__name__)
_TEXT_CHAR_THRESHOLD: int = 100
_SAMPLE_PAGES: int = 5


def detect_pdf_type(file_path: str) -> Tuple[PDFType, int]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    doc = fitz.open(str(path))
    total_pages: int = len(doc)
    if total_pages == 0:
        doc.close()
        logger.warning("pdf.detect.empty", file=file_path)
        return PDFType.TEXT, 0
    sample_count = min(_SAMPLE_PAGES, total_pages)
    indices = [int(i * (total_pages - 1) / max(sample_count - 1, 1)) for i in range(sample_count)]
    total_chars = 0
    for page_idx in indices:
        page = doc[page_idx]
        text = page.get_text("text")
        total_chars += len(text.strip())
    doc.close()
    avg_chars = total_chars / sample_count
    pdf_type = PDFType.TEXT if avg_chars >= _TEXT_CHAR_THRESHOLD else PDFType.SCANNED
    logger.info("pdf.detect.result", file=path.name, total_pages=total_pages, avg_chars=round(avg_chars, 1), pdf_type=pdf_type.value)
    return pdf_type, total_pages
