import pytest
from app.services.parsers.hindi_parser import parse_hindi_questions, _is_primarily_hindi
HINDI_TEXT = """1. भारत का सबसे बड़ा राज्य कौन सा है?
(A) राजस्थान
(B) मध्य प्रदेश
(C) उत्तर प्रदेश
(D) महाराष्ट्र
2. भारत का राष्ट्रीय पशु कौन सा है?
(A) शेर
(B) बाघ
(C) हाथी
(D) मोर
"""
def test_hindi_detection_with_hindi_text():
    assert _is_primarily_hindi("यह हिंदी में लिखा है") is True
def test_hindi_detection_with_english_text():
    assert _is_primarily_hindi("This is written in English") is False
def test_parse_hindi_returns_list():
    results = parse_hindi_questions(HINDI_TEXT, year=2023, exam="UPSC CSE", paper="GS-I", job_id="test")
    assert isinstance(results, list)
def test_parse_hindi_language_field():
    results = parse_hindi_questions(HINDI_TEXT, year=2023, exam="UPSC CSE", paper="GS-I", job_id="test")
    for q in results:
        assert q["language"] == "Hindi"
def test_empty_hindi_text():
    results = parse_hindi_questions("", year=2023, exam="UPSC", paper="GS-I", job_id="test")
    assert results == []
def test_english_text_ignored_in_hindi_parser():
    english_text = """1. What is the capital of France?
(A) London
(B) Paris
(C) Berlin
(D) Rome
"""
    results = parse_hindi_questions(english_text, year=2023, exam="UPSC", paper="GS-I", job_id="test")
    assert results == []
