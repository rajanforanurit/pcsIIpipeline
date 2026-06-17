import re
import unicodedata
from pathlib import Path
from typing import List
import fitz
from app.core.logging import get_logger
logger = get_logger(__name__)
def extract_text_from_pdf(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f'PDF not found: {file_path}')
    doc = fitz.open(str(path))
    page_texts: List[str] = []
    for page_num, page in enumerate(doc, start=1):
        page_text = _extract_page_text(page, page_num)
        if page_text.strip():
            page_texts.append(page_text)
    doc.close()
    combined = '\n\n'.join(page_texts)
    normalised = normalise_text(combined)
    logger.info('pdf.text_extracted', file=path.name, pages=len(page_texts), chars=len(normalised))
    return normalised
def _extract_page_text(page: fitz.Page, page_num: int) -> str:
    blocks = page.get_text('blocks')
    text_blocks = [(b[1], b[0], b[4]) for b in blocks if b[6] == 0]
    text_blocks.sort(key=lambda t: (round(t[0] / 10), t[1]))
    return '\n'.join((text for _, _, text in text_blocks))
def normalise_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    replacements = {'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '--', '\xa0': ' ', 'ﬁ': 'fi', 'ﬂ': 'fl'}
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    text = re.sub('\\n{3,}', '\n\n', text)
    return text.strip()
