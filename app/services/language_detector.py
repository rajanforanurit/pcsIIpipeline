import re
from typing import Any, Dict, List
_HINDI_CHAR_RANGE = re.compile('[\\u0900-\\u097F]')
_LATIN_CHAR_RANGE = re.compile('[A-Za-z]')
_DEFAULT_HINDI_LINE_THRESHOLD = 0.35
def is_hindi_line(text: str, threshold: float=_DEFAULT_HINDI_LINE_THRESHOLD) -> bool:
    if not text or not text.strip():
        return False
    hindi_chars = len(_HINDI_CHAR_RANGE.findall(text))
    latin_chars = len(_LATIN_CHAR_RANGE.findall(text))
    total_alpha = hindi_chars + latin_chars
    if total_alpha == 0:
        return False
    return hindi_chars / total_alpha >= threshold
def analyze_text(text: str) -> Dict[str, Any]:
    if not text:
        return {'hindi_ratio': 0.0, 'english_ratio': 0.0, 'hindi_char_count': 0, 'english_char_count': 0, 'total_alpha_chars': 0}
    hindi_chars = len(_HINDI_CHAR_RANGE.findall(text))
    latin_chars = len(_LATIN_CHAR_RANGE.findall(text))
    total_alpha = hindi_chars + latin_chars
    if total_alpha == 0:
        return {'hindi_ratio': 0.0, 'english_ratio': 0.0, 'hindi_char_count': 0, 'english_char_count': 0, 'total_alpha_chars': 0}
    return {'hindi_ratio': round(hindi_chars / total_alpha, 4), 'english_ratio': round(latin_chars / total_alpha, 4), 'hindi_char_count': hindi_chars, 'english_char_count': latin_chars, 'total_alpha_chars': total_alpha}
def analyze_lines(text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for line in text.split('\n'):
        entry = analyze_text(line)
        entry['line'] = line
        entry['is_hindi'] = is_hindi_line(line)
        results.append(entry)
    return results
