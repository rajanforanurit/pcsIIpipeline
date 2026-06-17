import re
from typing import Any, Dict, List
from app.services.language_detector import is_hindi_line
_NON_ALPHA_LINE = re.compile('^[\\s\\d\\W]*$')
def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if _NON_ALPHA_LINE.match(stripped):
        return True
    return False
def split_question_block(question_block: Dict[str, Any]) -> Dict[str, Any]:
    raw_block = question_block.get('raw_block', '') or ''
    question_no = question_block.get('question_no')
    english_lines: List[str] = []
    hindi_lines: List[str] = []
    for line in raw_block.split('\n'):
        if _is_noise_line(line):
            continue
        cleaned = line.strip()
        if is_hindi_line(cleaned):
            hindi_lines.append(cleaned)
        else:
            english_lines.append(cleaned)
    return {'question_no': question_no, 'english_text': '\n'.join(english_lines).strip(), 'hindi_text': '\n'.join(hindi_lines).strip()}
def split_question_blocks(question_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [split_question_block(block) for block in question_blocks]
