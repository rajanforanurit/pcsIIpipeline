import pytest
from app.services.validators.question_validator import validate_questions, generate_validation_report
VALID_Q = {
    "question_no": 1, "year": 2023, "exam": "UPSC CSE", "paper": "GS-I", "language": "English",
    "question": "What is the capital of India?",
    "options": {"A": "Mumbai", "B": "Delhi", "C": "Chennai", "D": "Kolkata"},
    "correct_answer": None, "job_id": "test123",
}
def test_valid_question_passes():
    valid, invalid = validate_questions([VALID_Q])
    assert len(valid) == 1
    assert len(invalid) == 0
def test_missing_question_text_fails():
    q = {**VALID_Q, "question": ""}
    valid, invalid = validate_questions([q])
    assert len(valid) == 0
    assert len(invalid) == 1
def test_missing_option_fails():
    q = {**VALID_Q, "options": {"A": "Mumbai", "B": "Delhi", "C": "Chennai"}}
    valid, invalid = validate_questions([q])
    assert len(invalid) == 1
def test_duplicate_question_number_fails():
    q2 = {**VALID_Q, "question": "Another question text here"}
    valid, invalid = validate_questions([VALID_Q, q2])
    assert len(valid) == 1
    assert len(invalid) == 1
def test_duplicate_question_text_fails():
    valid, invalid = validate_questions([VALID_Q, VALID_Q])
    assert len(invalid) == 1
def test_duplicate_options_fails():
    q = {**VALID_Q, "options": {"A": "Same", "B": "Same", "C": "Same", "D": "Same"}}
    valid, invalid = validate_questions([q])
    assert len(invalid) == 1
def test_validation_report_structure():
    valid, invalid = validate_questions([VALID_Q])
    report = generate_validation_report(valid, invalid, 1)
    assert "total_parsed" in report
    assert "valid_count" in report
    assert "invalid_count" in report
    assert "pass_rate_percent" in report
    assert report["pass_rate_percent"] == 100.0
