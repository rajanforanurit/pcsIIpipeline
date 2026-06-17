from typing import Any, Dict, List, Tuple

_REQUIRED_FIELDS = {"question_no", "question", "options", "year", "exam", "paper", "language"}
_OPTION_KEYS = {"A", "B", "C", "D"}
_MIN_QUESTION_LEN = 10
_MIN_OPTION_LEN = 1


def validate_questions(raw_questions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    seen_qnos: set = set()
    seen_questions: set = set()
    for idx, q in enumerate(raw_questions):
        errors = _validate_single(q, seen_qnos, seen_questions)
        if errors:
            invalid.append({"index": idx, "question_no": q.get("question_no"), "errors": errors, "data": q})
        else:
            seen_qnos.add(q["question_no"])
            seen_questions.add(q["question"].strip().lower()[:100])
            valid.append(q)
    return valid, invalid


def _validate_single(q: Dict[str, Any], seen_qnos: set, seen_questions: set) -> List[str]:
    errors: List[str] = []
    missing = _REQUIRED_FIELDS - set(q.keys())
    if missing:
        errors.append(f"Missing required fields: {missing}")
        return errors
    qno = q.get("question_no")
    if not isinstance(qno, int) or qno < 1:
        errors.append(f"Invalid question_no: {qno}")
    elif qno in seen_qnos:
        errors.append(f"Duplicate question_no: {qno}")
    question_text = q.get("question", "")
    if not question_text or not isinstance(question_text, str):
        errors.append("Question text is missing or not a string")
    elif len(question_text.strip()) < _MIN_QUESTION_LEN:
        errors.append(f"Question text too short (< {_MIN_QUESTION_LEN} chars)")
    else:
        norm = question_text.strip().lower()[:100]
        if norm in seen_questions:
            errors.append("Duplicate question text detected")
    options = q.get("options", {})
    if not isinstance(options, dict):
        errors.append("Options must be a dictionary")
    else:
        missing_opts = _OPTION_KEYS - set(options.keys())
        if missing_opts:
            errors.append(f"Missing options: {missing_opts}")
        else:
            opt_values = []
            for key in _OPTION_KEYS:
                val = options.get(key, "")
                if not val or len(str(val).strip()) < _MIN_OPTION_LEN:
                    errors.append(f"Option {key} is empty or too short")
                else:
                    opt_values.append(str(val).strip().lower())
            if len(opt_values) == 4 and len(set(opt_values)) < 4:
                errors.append("Duplicate option values detected")
    year = q.get("year")
    if not isinstance(year, int) or not (1900 <= year <= 2100):
        errors.append(f"Invalid year: {year}")
    if not q.get("exam"):
        errors.append("Exam field is empty")
    if not q.get("paper"):
        errors.append("Paper field is empty")
    return errors


def generate_validation_report(valid: List[Dict[str, Any]], invalid: List[Dict[str, Any]], total_parsed: int) -> Dict[str, Any]:
    return {
        "total_parsed": total_parsed,
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "pass_rate_percent": round(len(valid) / total_parsed * 100, 2) if total_parsed > 0 else 0,
        "issues": invalid[:50],
    }
