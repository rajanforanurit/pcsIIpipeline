"""Validate questions produced by the Drive pipeline against the canonical schema."""
from typing import Any, Dict, List, Tuple


_REQUIRED_FIELDS = ("id", "year", "exam", "paper", "language", "question", "options", "correct_answer")
_VALID_ANSWERS = {"A", "B", "C", "D"}
_VALID_LANGUAGES = {"English", "Hindi"}


def validate_pipeline_questions(questions: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """
    Validate a list of question dicts against the canonical schema.
    Returns (valid, invalid).
    """
    valid: List[Dict] = []
    invalid: List[Dict] = []

    for q in questions:
        errors: List[str] = []

        # Required fields
        for field in _REQUIRED_FIELDS:
            if field not in q:
                errors.append(f"Missing field: {field}")

        # Options shape
        opts = q.get("options", {})
        if not isinstance(opts, dict):
            errors.append("options must be a dict")
        else:
            for key in ("A", "B", "C", "D"):
                if key not in opts:
                    errors.append(f"Missing option key: {key}")
                elif not str(opts[key]).strip():
                    errors.append(f"Empty option: {key}")

        # correct_answer
        ca = q.get("correct_answer")
        if ca is not None and str(ca).upper() not in _VALID_ANSWERS:
            errors.append(f"Invalid correct_answer: {ca}")

        # question text
        if not str(q.get("question", "")).strip():
            errors.append("question text is empty")

        # year
        year = q.get("year")
        if year is not None:
            try:
                y = int(year)
                if not (1900 <= y <= 2100):
                    errors.append(f"year out of range: {year}")
            except (TypeError, ValueError):
                errors.append(f"Invalid year: {year}")

        if errors:
            q["_validation_errors"] = errors
            invalid.append(q)
        else:
            valid.append(q)

    return valid, invalid


def normalise_question(q: Dict[str, Any]) -> Dict[str, Any]:
    """Return a clean copy of a question dict matching the exact JSON schema."""
    ca = q.get("correct_answer")
    return {
        "id": int(q["id"]),
        "year": int(q["year"]) if q.get("year") else None,
        "exam": str(q.get("exam", "")).strip(),
        "paper": str(q.get("paper", "")).strip(),
        "language": str(q.get("language", "English")).strip(),
        "question": str(q["question"]).strip(),
        "options": {
            "A": str(q["options"]["A"]).strip(),
            "B": str(q["options"]["B"]).strip(),
            "C": str(q["options"]["C"]).strip(),
            "D": str(q["options"]["D"]).strip(),
        },
        "correct_answer": str(ca).upper() if ca else None,
    }
