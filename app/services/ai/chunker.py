import re
from typing import List
_MIN_CHUNK = 500
_MAX_CHUNK = 3000
_OVERLAP = 100
def chunk_text(text: str, max_chunk_size: int=_MAX_CHUNK, min_chunk_size: int=_MIN_CHUNK, overlap: int=_OVERLAP) -> List[str]:
    if not text or not text.strip():
        return []
    paragraphs = re.split('\\n{2,}', text.strip())
    chunks: List[str] = []
    current_chunk = ''
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk = (current_chunk + '\n\n' + para).strip()
        else:
            if current_chunk and len(current_chunk) >= min_chunk_size:
                chunks.append(current_chunk)
            if len(para) > max_chunk_size:
                sub_chunks = _split_large_paragraph(para, max_chunk_size, overlap)
                chunks.extend(sub_chunks[:-1])
                current_chunk = sub_chunks[-1] if sub_chunks else ''
            elif current_chunk and overlap > 0:
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = (overlap_text + '\n\n' + para).strip()
            else:
                current_chunk = para
    if current_chunk and len(current_chunk) >= min_chunk_size:
        chunks.append(current_chunk)
    elif current_chunk and chunks:
        chunks[-1] = chunks[-1] + '\n\n' + current_chunk
    elif current_chunk:
        chunks.append(current_chunk)
    return [c for c in chunks if c.strip()]
def _split_large_paragraph(text: str, max_size: int, overlap: int) -> List[str]:
    sentences = re.split('(?<=[.!?])\\s+', text)
    chunks: List[str] = []
    current = ''
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_size:
            current = (current + ' ' + sentence).strip()
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_size:
                for i in range(0, len(sentence), max_size - overlap):
                    chunks.append(sentence[i:i + max_size])
                current = ''
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks
