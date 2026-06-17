import asyncio
from pathlib import Path
from typing import List, Optional
import cv2
import fitz
import numpy as np
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ocr_engine = None


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang=settings.OCR_LANGUAGE,
                use_gpu=settings.PADDLE_USE_GPU,
                show_log=False,
            )
            logger.info("ocr.engine_initialized", lang=settings.OCR_LANGUAGE)
        except ImportError:
            logger.warning("ocr.paddleocr_not_available")
            _ocr_engine = None
    return _ocr_engine


def _preprocess_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    coords = np.column_stack(np.where(gray > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 0.5:
        h, w = gray.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _extract_page_image(doc: fitz.Document, page_idx: int, dpi: int = 200) -> np.ndarray:
    page = doc[page_idx]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return img_array.copy()


def _ocr_image(engine, image: np.ndarray) -> str:
    if engine is None:
        return ""
    result = engine.ocr(image, cls=True)
    if not result or not result[0]:
        return ""
    lines = []
    for line in result[0]:
        if line and len(line) >= 2 and line[1] and len(line[1]) >= 1:
            text = line[1][0]
            confidence = line[1][1] if len(line[1]) > 1 else 0
            if confidence > 0.5 and text.strip():
                lines.append(text.strip())
    return "\n".join(lines)


async def extract_text_from_scanned_pdf(file_path: str, progress_callback=None) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    engine = _get_ocr_engine()
    if engine is None:
        from app.services.text_extractor import extract_text_from_pdf
        logger.warning("ocr.fallback_to_text_extraction")
        return extract_text_from_pdf(file_path)
    doc = fitz.open(str(path))
    total_pages = len(doc)
    page_texts: List[str] = []
    loop = asyncio.get_event_loop()
    for page_idx in range(total_pages):
        image = await loop.run_in_executor(None, _extract_page_image, doc, page_idx)
        processed = await loop.run_in_executor(None, _preprocess_image, image)
        text = await loop.run_in_executor(None, _ocr_image, engine, processed)
        if text.strip():
            page_texts.append(text)
        if progress_callback:
            pct = ((page_idx + 1) / total_pages) * 100
            await progress_callback(pct)
        logger.debug("ocr.page_processed", page=page_idx + 1, total=total_pages, chars=len(text))
    doc.close()
    full_text = "\n\n".join(page_texts)
    logger.info("ocr.extraction_complete", file=path.name, pages=total_pages, chars=len(full_text))
    return full_text
