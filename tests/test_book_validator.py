import pytest
from app.services.validators.book_question_validator import validate_book_questions, generate_book_validation_report
VALID_Q = {
    "question": "Which article of the Indian Constitution deals with freedom of speech?",
    "options": {"A": "Article 19", "B": "Article 21", "C": "Article 32", "D": "Article 14"},
    "correct_answer": "A",
    "explanation": "Article 19 guarantees freedom of speech and expression.",
    "chunk_index": 0,
}
def test_valid_book_question_passes():
    valid, invalid = validate_book_questions([VALID_Q])
    assert len(valid) == 1
    assert len(invalid) == 0
def test_invalid_correct_answer_fails():
    q = {**VALID_Q, "correct_answer": "E"}
    valid, invalid = validate_book_questions([q])
    assert len(invalid) == 1
def test_short_question_fails():
    q = {**VALID_Q, "question": "What?"}
    valid, invalid = validate_book_questions([q])
    assert len(invalid) == 1
def test_duplicate_book_question_fails():
    valid, invalid = validate_book_questions([VALID_Q, VALID_Q])
    assert len(invalid) == 1
def test_duplicate_options_fails():
    q = {**VALID_Q, "options": {"A": "Same", "B": "Same", "C": "Same", "D": "Same"}}
    valid, invalid = validate_book_questions([q])
    assert len(invalid) == 1
def test_missing_options_key_fails():
    q = {**VALID_Q, "options": {"A": "Only one"}}
    valid, invalid = validate_book_questions([q])
    assert len(invalid) == 1
def test_report_generation():
    valid, invalid = validate_book_questions([VALID_Q])
    report = generate_book_validation_report(valid, invalid, 1)
    assert report["total_generated"] == 1
    assert report["valid_count"] == 1
    assert report["pass_rate_percent"] == 100.0
