import re
from typing import Any, Dict, List
_NUMBERED_DOT = re.compile('^[ \\t]*(\\d{1,3})[.)]\\s+', re.MULTILINE)
_Q_PREFIX = re.compile('^[ \\t]*Q\\.?\\s*(\\d{1,3})[.):]?\\s+', re.MULTILINE | re.IGNORECASE)
_QUESTION_PREFIX = re.compile('^[ \\t]*(?:Question|Ques\\.?)\\s*(\\d{1,3})[.):]?\\s+', re.MULTILINE | re.IGNORECASE)
_HINDI_PRASHN = re.compile('^[ \\t]*(?:प्रश्न|प्र\\.?)\\s*[-:.]?\\s*(\\d{1,3})[.):।]?\\s*', re.MULTILINE)
_ALL_PATTERNS = [_NUMBERED_DOT, _Q_PREFIX, _QUESTION_PREFIX, _HINDI_PRASHN]
_MAX_QUESTION_NO = 999
def _find_all_matches(text: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for pattern in _ALL_PATTERNS:
        for m in pattern.finditer(text):
            qno_str = m.group(1)
            if not qno_str:
                continue
            try:
                qno = int(qno_str)
            except ValueError:
                continue
            if qno < 1 or qno > _MAX_QUESTION_NO:
                continue
            matches.append({'start': m.start(), 'end': m.end(), 'question_no': qno})
    matches.sort(key=lambda x: x['start'])
    return matches
def _dedupe_by_question_no(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for m in matches:
        if m['question_no'] in seen:
            continue
        seen.add(m['question_no'])
        deduped.append(m)
    return deduped
def detect_question_boundaries(text: str) -> List[Dict[str, Any]]:
    if not text or not text.strip():
        return []
    matches = _find_all_matches(text)
    if not matches:
        return []
    deduped = _dedupe_by_question_no(matches)
    blocks: List[Dict[str, Any]] = []
    for idx, m in enumerate(deduped):
        block_start = m['end']
        block_end = deduped[idx + 1]['start'] if idx + 1 < len(deduped) else len(text)
        raw_block = text[block_start:block_end].strip()
        if not raw_block:
            continue
        blocks.append({'question_no': m['question_no'], 'raw_block': raw_block})
    return blocks
def strip_leading_question_marker(text: str) -> str:
    if not text:
        return text
    for pattern in _ALL_PATTERNS:
        m = pattern.match(text)
        if m:
            return text[m.end():].strip()
    return text
