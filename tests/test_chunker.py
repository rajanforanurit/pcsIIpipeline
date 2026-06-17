import pytest
from app.services.ai.chunker import chunk_text
def test_chunk_empty_text():
    assert chunk_text("") == []
def test_chunk_short_text_returns_single_chunk():
    text = "This is a short paragraph about Indian history.\n\nAnother small paragraph here."
    chunks = chunk_text(text, min_chunk_size=10)
    assert len(chunks) >= 1
def test_chunk_respects_max_size():
    long_text = ("word " * 1000).strip()
    chunks = chunk_text(long_text, max_chunk_size=500)
    for chunk in chunks:
        assert len(chunk) <= 600
def test_chunk_returns_non_empty_strings():
    text = "Para one.\n\nPara two.\n\nPara three about geography.\n\nPara four about polity."
    chunks = chunk_text(text, min_chunk_size=5)
    for chunk in chunks:
        assert chunk.strip() != ""
def test_chunk_large_pdf_content():
    import random
    sentences = ["This is sentence number {i} about Indian constitutional history. ".format(i=i) for i in range(500)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_chunk_size=2000, min_chunk_size=300)
    assert len(chunks) > 1
    total_words = sum(len(c.split()) for c in chunks)
    assert total_words > 0
