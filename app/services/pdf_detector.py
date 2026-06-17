import re
from pathlib import Path
from typing import Tuple
import fitz
from app.core.config import settings
from app.core.logging import get_logger
from app.models.common import PDFType
logger = get_logger(__name__)
_TEXT_CHAR_THRESHOLD: int = 100
_SAMPLE_PAGES: int = 5
_REPLACEMENT_CHAR = '�'
_WORD_TOKEN = re.compile('[A-Za-z\\u0900-\\u097F]{2,}')
def assess_text_quality(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    total_chars = len(text)
    replacement_count = text.count(_REPLACEMENT_CHAR)
    alnum_count = sum((1 for c in text if c.isalnum()))
    alnum_ratio = alnum_count / total_chars if total_chars else 0.0
    tokens = text.split()
    word_tokens = _WORD_TOKEN.findall(text)
    word_ratio = len(word_tokens) / len(tokens) if tokens else 0.0
    replacement_penalty = min(replacement_count / max(total_chars, 1) * 50, 1.0)
    score = alnum_ratio * 0.5 + word_ratio * 0.5 - replacement_penalty
    return max(0.0, min(1.0, round(score, 4)))
def detect_pdf_type(file_path: str) -> Tuple[PDFType, int]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f'PDF not found: {file_path}')
    doc = fitz.open(str(path))
    total_pages: int = len(doc)
    if total_pages == 0:
        doc.close()
        logger.warning('pdf.detect.empty', file=file_path)
        return (PDFType.TEXT, 0)
    sample_count = min(_SAMPLE_PAGES, total_pages)
    indices = [int(i * (total_pages - 1) / max(sample_count - 1, 1)) for i in range(sample_count)]
    total_chars = 0
    sample_texts = []
    for page_idx in indices:
        page = doc[page_idx]
        text = page.get_text('text')
        total_chars += len(text.strip())
        sample_texts.append(text)
    doc.close()
    avg_chars = total_chars / sample_count
    combined_sample = '\n'.join(sample_texts)
    quality_score = assess_text_quality(combined_sample)
    if avg_chars < _TEXT_CHAR_THRESHOLD:
        pdf_type = PDFType.SCANNED
    elif quality_score < settings.OCR_TEXT_QUALITY_THRESHOLD:
        pdf_type = PDFType.SCANNED
    else:
        pdf_type = PDFType.TEXT
    logger.info('pdf.detect.result', file=path.name, total_pages=total_pages, avg_chars=round(avg_chars, 1), quality_score=quality_score, pdf_type=pdf_type.value)
    return (pdf_type, total_pages)
