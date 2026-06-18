import json
import re
import time
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.exceptions import AIProviderError, AIProviderNotConfiguredError
from app.core.logging import get_logger
from app.models.common import DocumentType

logger = get_logger(__name__)

_DOCUMENT_TYPES = [e.value for e in DocumentType]

_SYSTEM_PROMPT = """\
You are an expert UPSC/JPSC/UPPCS bilingual exam question extractor.

The PDF text you receive may contain questions in ONE of these formats:
  FORMAT A - English only: numbered questions with (a)(b)(c)(d) or (A)(B)(C)(D) options
  FORMAT B - Hindi only: numbered questions with Devanagari text
  FORMAT C - Bilingual interleaved: English question followed immediately by its Hindi translation, then options in both languages
  FORMAT D - Bilingual side-by-side or mixed: both languages present but in varying order

YOUR TASK:
1. Detect the document type from: UPSC PYQ | UPPCS PYQ | JPSC PYQ | History Book | Polity Book | Geography Book | Economy Book | Environment | Science | Current Affairs | Other
2. Extract the year and exam name from any context clues (headers, footers, question numbering).
3. Extract EVERY numbered multiple-choice question visible in the text.
4. For each question number, pair the English and Hindi versions together.

CRITICAL EXTRACTION RULES:
- A question starts with a number like: 1. or 1) or Q.1 or Q1.
- Options are labelled (a) (b) (c) (d) OR (A) (B) (C) (D) OR a. b. c. d.
- If only English is present, fill "english" and set "hindi" to null.
- If only Hindi is present, fill "hindi" and set "english" to null.
- If both are present, fill both "english" and "hindi".
- NEVER skip a question just because one language is missing.
- NEVER invent or translate — only extract what is literally in the text.
- answer should be the correct option letter if visible, else null.
- If options are labelled (a)(b)(c)(d) lowercase, map them to A B C D uppercase.

OUTPUT: Return ONLY a valid JSON object — no markdown fences, no explanation, no extra text:
{
  "document_type": "JPSC PYQ",
  "year": 2023,
  "exam": "JPSC Prelims",
  "questions": [
    {
      "id": 1,
      "year": 2023,
      "exam": "JPSC Prelims",
      "english": {
        "question": "Full English question text?",
        "options": {"A": "...", "B": "...", "C": "...", "D": "..."}
      },
      "hindi": {
        "question": "Full Hindi question text?",
        "options": {"A": "...", "B": "...", "C": "...", "D": "..."}
      },
      "answer": null
    }
  ]
}
"""


class DriveAIProvider:
    def __init__(self) -> None:
        if not settings.ai_configured:
            raise AIProviderNotConfiguredError()
        self._endpoint = settings.PCS2.rstrip('/')
        self._api_key = settings.PCS2_API
        self._model = settings.AI_MODEL_DEPLOYMENT
        self._client = httpx.AsyncClient(
            timeout=240.0,
            headers={
                'Authorization': f'Bearer {self._api_key}',
                'Content-Type': 'application/json',
            },
        )

    async def extract_questions(self, ocr_text: str, chunk_index: int = 0) -> Dict[str, Any]:
        url = f'{self._endpoint}?api-version=2024-05-01-preview'
        user_prompt = (
            'Extract ALL numbered MCQ questions from the text below. '
            'Pair English and Hindi versions of the same question together. '
            'Return ONLY the JSON object — no markdown, no extra text.\n\n'
            f'TEXT:\n{ocr_text}'
        )
        payload = {
            'model': self._model,
            'messages': [
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': 12000,
            'temperature': 0.05,
            'top_p': 0.95,
        }
        try:
            t0 = time.monotonic()
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            elapsed = time.monotonic() - t0
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            tokens = data.get('usage', {}).get('total_tokens', 0)
            logger.info(
                'blob_ai.response_received',
                chunk_index=chunk_index,
                tokens=tokens,
                elapsed_s=round(elapsed, 2),
            )
            return self._parse_response(content, chunk_index)
        except httpx.HTTPStatusError as e:
            logger.error('blob_ai.http_error', status=e.response.status_code, chunk_index=chunk_index)
            raise AIProviderError(f'HTTP {e.response.status_code}: {e.response.text[:200]}', provider='azure')
        except httpx.RequestError as e:
            logger.error('blob_ai.request_error', error=str(e), chunk_index=chunk_index)
            raise AIProviderError(f'Request failed: {str(e)}', provider='azure')
        except (KeyError, IndexError) as e:
            logger.error('blob_ai.parse_error', error=str(e))
            raise AIProviderError(f'Unexpected response structure: {str(e)}', provider='azure')

    def _parse_response(self, content: str, chunk_index: int) -> Dict[str, Any]:
        # Strip markdown fences if present
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)
        content = content.strip()

        # Try direct parse first
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Fall back: find outermost JSON object
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                logger.warning('blob_ai.no_json_found', chunk_index=chunk_index, preview=content[:200])
                return self._empty_result()
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError as exc:
                logger.error('blob_ai.json_decode_error', error=str(exc), chunk_index=chunk_index)
                return self._empty_result()

        questions = result.get('questions', [])
        validated: List[Dict[str, Any]] = []

        for idx, q in enumerate(questions, start=1):
            if not isinstance(q, dict):
                continue

            english = self._validate_lang_section(q.get('english'))
            hindi = self._validate_lang_section(q.get('hindi'))

            if english is None and hindi is None:
                logger.debug('blob_ai.question_skipped_no_langs', id=q.get('id', idx))
                continue

            answer = q.get('answer')
            if answer is not None:
                answer = str(answer).upper().strip()
                if answer not in {'A', 'B', 'C', 'D'}:
                    answer = None

            validated.append({
                'id': q.get('id', idx),
                'year': q.get('year') or result.get('year'),
                'exam': q.get('exam') or result.get('exam') or '',
                'english': english,
                'hindi': hindi,
                'answer': answer,
            })

        logger.info('blob_ai.questions_parsed', count=len(validated), chunk_index=chunk_index)
        return {
            'document_type': result.get('document_type', 'Other'),
            'year': result.get('year'),
            'exam': result.get('exam', ''),
            'questions': validated,
        }

    def _validate_lang_section(self, section: Any) -> Any:
        if section is None:
            return None
        if not isinstance(section, dict):
            return None
        question = section.get('question', '').strip()
        if not question:
            return None
        opts = section.get('options', {})
        if not isinstance(opts, dict):
            return None
        # Must have all 4 options; normalize lowercase a/b/c/d to A/B/C/D
        normalized: Dict[str, str] = {}
        for k, v in opts.items():
            normalized[k.upper()] = str(v).strip()
        if not all(k in normalized for k in ('A', 'B', 'C', 'D')):
            return None
        return {
            'question': question,
            'options': {
                'A': normalized['A'],
                'B': normalized['B'],
                'C': normalized['C'],
                'D': normalized['D'],
            },
        }

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {'document_type': 'Other', 'year': None, 'exam': '', 'questions': []}

    async def close(self) -> None:
        await self._client.aclose()
