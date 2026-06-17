import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.core.config import settings
from app.core.exceptions import AIProviderError, AIProviderNotConfiguredError
from app.core.logging import get_logger
from app.models.common import DocumentType
logger = get_logger(__name__)
_DOCUMENT_TYPES = [e.value for e in DocumentType]
_SYSTEM_PROMPT = 'You are an expert UPSC/UPPCS exam question extractor.\n\nYour job:\n1. Detect the language of the document: "English" or "Hindi"\n2. Detect the document type from this list:\n   UPSC PYQ | UPPCS PYQ | History Book | Polity Book | Geography Book | Economy Book | Environment | Science | Current Affairs | Other\n3. Extract the year, exam name, and paper name from context clues in the text.\n4. Extract ALL multiple-choice questions from the text.\n\nSTRICT OUTPUT FORMAT – return ONLY valid JSON, no markdown, no extra text:\n{\n  "language": "English",\n  "document_type": "UPSC PYQ",\n  "year": 2023,\n  "exam": "UPSC Prelims",\n  "paper": "GS Paper 1",\n  "questions": [\n    {\n      "id": 1,\n      "year": 2023,\n      "exam": "UPSC Prelims",\n      "paper": "GS Paper 1",\n      "language": "English",\n      "question": "Full question text here?",\n      "options": {\n        "A": "Option A text",\n        "B": "Option B text",\n        "C": "Option C text",\n        "D": "Option D text"\n      },\n      "correct_answer": "B"\n    }\n  ]\n}\n\nRules:\n- Every question MUST have exactly 4 options (A, B, C, D).\n- correct_answer must be one of: A, B, C, D (use null if not present in text).\n- Keep question text verbatim from the source.\n- If year/exam/paper cannot be determined, use null.\n- Do NOT add any fields beyond what is shown above.\n- Return ONLY the JSON object, nothing else.\n'
class DriveAIProvider:
    def __init__(self) -> None:
        if not settings.ai_configured:
            raise AIProviderNotConfiguredError()
        self._endpoint = settings.PCS2.rstrip('/')
        self._api_key = settings.PCS2_API
        self._model = settings.AI_MODEL_DEPLOYMENT
        self._client = httpx.AsyncClient(timeout=180.0, headers={'Authorization': f'Bearer {self._api_key}', 'Content-Type': 'application/json'})
    async def extract_questions(self, ocr_text: str, chunk_index: int=0) -> Dict[str, Any]:
        url = f'{self._endpoint}?api-version=2024-05-01-preview'
        user_prompt = f'Extract all MCQ questions from the following text. Return ONLY valid JSON as specified.\n\nText:\n{ocr_text}'
        payload = {'model': self._model, 'messages': [{'role': 'system', 'content': _SYSTEM_PROMPT}, {'role': 'user', 'content': user_prompt}], 'max_tokens': 8000, 'temperature': 0.1, 'top_p': 0.95}
        try:
            t0 = time.monotonic()
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            elapsed = time.monotonic() - t0
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            tokens = data.get('usage', {}).get('total_tokens', 0)
            logger.info('drive_ai.response_received', chunk_index=chunk_index, tokens=tokens, elapsed_s=round(elapsed, 2))
            return self._parse_response(content, chunk_index)
        except httpx.HTTPStatusError as e:
            logger.error('drive_ai.http_error', status=e.response.status_code, chunk_index=chunk_index)
            raise AIProviderError(f'HTTP {e.response.status_code}: {e.response.text[:200]}', provider='azure')
        except httpx.RequestError as e:
            logger.error('drive_ai.request_error', error=str(e), chunk_index=chunk_index)
            raise AIProviderError(f'Request failed: {str(e)}', provider='azure')
        except (KeyError, IndexError) as e:
            logger.error('drive_ai.parse_error', error=str(e))
            raise AIProviderError(f'Unexpected response structure: {str(e)}', provider='azure')
    def _parse_response(self, content: str, chunk_index: int) -> Dict[str, Any]:
        content = re.sub('^```(?:json)?\\s*', '', content, flags=re.MULTILINE)
        content = re.sub('\\s*```$', '', content, flags=re.MULTILINE)
        content = content.strip()
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search('\\{.*\\}', content, re.DOTALL)
            if not match:
                logger.warning('drive_ai.no_json_found', chunk_index=chunk_index)
                return self._empty_result()
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError as exc:
                logger.error('drive_ai.json_decode_error', error=str(exc), chunk_index=chunk_index)
                return self._empty_result()
        questions = result.get('questions', [])
        validated: List[Dict[str, Any]] = []
        for idx, q in enumerate(questions, start=1):
            if not isinstance(q, dict):
                continue
            if not all((k in q for k in ('question', 'options'))):
                continue
            opts = q.get('options', {})
            if not isinstance(opts, dict) or not all((k in opts for k in ('A', 'B', 'C', 'D'))):
                continue
            ca = q.get('correct_answer')
            if ca is not None:
                ca = str(ca).upper()
                if ca not in {'A', 'B', 'C', 'D'}:
                    ca = None
            validated.append({'id': q.get('id', idx), 'year': q.get('year') or result.get('year'), 'exam': q.get('exam') or result.get('exam') or '', 'paper': q.get('paper') or result.get('paper') or '', 'language': q.get('language') or result.get('language') or 'English', 'question': str(q['question']).strip(), 'options': {'A': str(opts['A']).strip(), 'B': str(opts['B']).strip(), 'C': str(opts['C']).strip(), 'D': str(opts['D']).strip()}, 'correct_answer': ca})
        logger.info('drive_ai.questions_parsed', count=len(validated), chunk_index=chunk_index)
        return {'language': result.get('language', 'English'), 'document_type': result.get('document_type', 'Other'), 'year': result.get('year'), 'exam': result.get('exam', ''), 'paper': result.get('paper', ''), 'questions': validated}
    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {'language': 'English', 'document_type': 'Other', 'year': None, 'exam': '', 'paper': '', 'questions': []}
    async def close(self) -> None:
        await self._client.aclose()
