from typing import Any, Dict, List, Tuple
_REQUIRED = {'question', 'options', 'correct_answer', 'chunk_index'}
_OPTION_KEYS = {'A', 'B', 'C', 'D'}
def validate_book_questions(raw_questions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    seen_questions: set = set()
    for idx, q in enumerate(raw_questions):
        errors = _validate_single(q, seen_questions)
        if errors:
            invalid.append({'index': idx, 'errors': errors, 'data': q})
        else:
            norm = q['question'].strip().lower()[:100]
            seen_questions.add(norm)
            valid.append(q)
    return (valid, invalid)
def _validate_single(q: Dict[str, Any], seen_questions: set) -> List[str]:
    errors: List[str] = []
    missing = _REQUIRED - set(q.keys())
    if missing:
        errors.append(f'Missing fields: {missing}')
        return errors
    question_text = q.get('question', '')
    if not question_text or len(str(question_text).strip()) < 10:
        errors.append('Question text too short or empty')
    else:
        norm = str(question_text).strip().lower()[:100]
        if norm in seen_questions:
            errors.append('Duplicate question')
    options = q.get('options', {})
    if not isinstance(options, dict):
        errors.append('Options must be a dictionary')
    else:
        missing_opts = _OPTION_KEYS - set(options.keys())
        if missing_opts:
            errors.append(f'Missing options: {missing_opts}')
        else:
            opt_vals = [str(options[k]).strip().lower() for k in _OPTION_KEYS]
            for i, k in enumerate(_OPTION_KEYS):
                if not str(options.get(k, '')).strip():
                    errors.append(f'Option {k} is empty')
            if len(set(opt_vals)) < 4:
                errors.append('Duplicate option values')
    answer = q.get('correct_answer', '')
    if not answer or str(answer).upper() not in _OPTION_KEYS:
        errors.append(f'Invalid correct_answer: {answer!r}')
    return errors
def generate_book_validation_report(valid: List[Dict], invalid: List[Dict], total: int) -> Dict[str, Any]:
    return {'total_generated': total, 'valid_count': len(valid), 'invalid_count': len(invalid), 'pass_rate_percent': round(len(valid) / total * 100, 2) if total > 0 else 0, 'issues': invalid[:50]}
