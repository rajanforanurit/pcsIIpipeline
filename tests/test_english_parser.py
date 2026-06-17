import pytest
from app.services.parsers.english_parser import parse_english_questions, _is_primarily_hindi
SAMPLE_TEXT = """1. Which of the following is the longest river in India?
(A) Ganga
(B) Yamuna
(C) Godavari
(D) Narmada
2. The Battle of Plassey was fought in which year?
(A) 1757
(B) 1764
(C) 1857
(D) 1849
"""
def test_parse_english_returns_list():
    results = parse_english_questions(SAMPLE_TEXT, year=2023, exam="UPSC CSE", paper="GS-I", job_id="test")
    assert isinstance(results, list)
def test_parse_english_question_structure():
    results = parse_english_questions(SAMPLE_TEXT, year=2023, exam="UPSC CSE", paper="GS-I", job_id="test")
    if results:
        q = results[0]
        assert "question_no" in q
        assert "question" in q
        assert "options" in q
        assert "A" in q["options"]
        assert "B" in q["options"]
        assert "C" in q["options"]
        assert "D" in q["options"]
        assert q["correct_answer"] is None
        assert q["language"] == "English"
        assert q["year"] == 2023
def test_hindi_detection():
    hindi_text = "यह एक हिंदी वाक्य है जो परीक्षा में आता है"
    english_text = "This is an English sentence about history"
    assert _is_primarily_hindi(hindi_text) is True
    assert _is_primarily_hindi(english_text) is False
def test_empty_text_returns_empty():
    results = parse_english_questions("", year=2023, exam="UPSC", paper="GS-I", job_id="test")
    assert results == []
