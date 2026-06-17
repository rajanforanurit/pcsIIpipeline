import re
from typing import Any, Dict, List, Optional, Tuple
_Q_PATTERNS = [re.compile('^(\\d{1,3})[.)]\\s+(.+)', re.MULTILINE), re.compile('^Q\\.?\\s*(\\d{1,3})[.):]?\\s+(.+)', re.MULTILINE), re.compile('^(?:Question|Ques\\.?)\\s*(\\d{1,3})[.):]?\\s+(.+)', re.MULTILINE | re.IGNORECASE)]
_OPT_PATTERN = re.compile('^\\s*\\(?\\s*([A-Da-d])\\s*[).\\-:]\\s*(.+)', re.MULTILINE)
_OPT_INLINE = re.compile('\\b([A-Da-d])\\s*[).\\-:]\\s*(.+?)(?=\\s+[A-Da-d]\\s*[).\\-:]|$)', re.DOTALL)
_HINDI_RANGE = re.compile('[\\u0900-\\u097F]')
def _is_primarily_hindi(text: str) -> bool:
    hindi_chars = len(_HINDI_RANGE.findall(text))
    total_alpha = sum((1 for c in text if c.isalpha()))
    if total_alpha == 0:
        return False
    return hindi_chars / total_alpha > 0.4
def _extract_question_blocks(text: str) -> List[Tuple[int, str, int, int]]:
    blocks: List[Tuple[int, int, int, str]] = []
    for pattern in _Q_PATTERNS:
        for m in pattern.finditer(text):
            qno = int(m.group(1))
            start = m.start()
            blocks.append((start, m.end(), qno, m.group(2).strip()))
    if not blocks:
        return []
    blocks.sort(key=lambda x: x[0])
    seen_qnos = set()
    deduped = []
    for block in blocks:
        if block[2] not in seen_qnos:
            seen_qnos.add(block[2])
            deduped.append(block)
    result = []
    for i, (start, end, qno, q_start) in enumerate(deduped):
        next_start = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        full_block = q_start + '\n' + text[end:next_start].strip()
        result.append((qno, full_block, start, next_start))
    return result
def _parse_options_from_block(block_text: str) -> Optional[Dict[str, str]]:
    opts: Dict[str, str] = {}
    matches = _OPT_PATTERN.findall(block_text)
    for key, val in matches:
        k = key.upper()
        if k in {'A', 'B', 'C', 'D'} and k not in opts:
            opts[k] = val.strip()
    if len(opts) >= 4:
        return opts
    opts = {}
    matches = _OPT_INLINE.findall(block_text)
    for key, val in matches:
        k = key.upper()
        if k in {'A', 'B', 'C', 'D'} and k not in opts:
            opts[k] = val.strip()
    if len(opts) >= 4:
        return opts
    return None
def _clean_question_text(text: str) -> str:
    lines = text.split('\n')
    question_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match('^\\(?\\s*[A-Da-d]\\s*[).\\-:]', stripped):
            break
        question_lines.append(stripped)
    return ' '.join(question_lines).strip()
def parse_english_questions(text: str, year: int, exam: str, paper: str, set_name: Optional[str]=None, job_id: str='') -> List[Dict[str, Any]]:
    blocks = _extract_question_blocks(text)
    parsed: List[Dict[str, Any]] = []
    for qno, block_text, _, _ in blocks:
        if _is_primarily_hindi(block_text):
            continue
        options = _parse_options_from_block(block_text)
        if options is None or len(options) < 4:
            continue
        question_text = _clean_question_text(block_text)
        if not question_text or len(question_text) < 10:
            continue
        parsed.append({'job_id': job_id, 'question_no': qno, 'year': year, 'exam': exam, 'paper': paper, 'language': 'English', 'set_name': set_name, 'question': question_text, 'options': {'A': options.get('A', ''), 'B': options.get('B', ''), 'C': options.get('C', ''), 'D': options.get('D', '')}, 'correct_answer': None})
    return parsed
