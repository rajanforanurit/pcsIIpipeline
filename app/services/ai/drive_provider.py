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

_SYSTEM_PROMPT = (
    'You are an expert UPSC/UPPCS bilingual exam question extractor.\n\n'
    'Your job:\n'
    '1. Detect the document type from this list:\n'
    '   UPSC PYQ | UPPCS PYQ | History Book | Polity Book | Geography Book | Economy Book | Environment | Science | Current Affairs | Other\n'
    '2. Extract the year and exam name from context clues in the text.\n'
    '3. Extract ALL multiple-choice questions from the text.\n'
    '4. For each question, extract both English and Hindi versions if present.\n\n'
    'STRICT OUTPUT FORMAT – return ONLY valid JSON, no markdown, no extra text:\n'
    '{\n'
    '  "document_type": "UPSC PYQ",\n'
    '  "year": 2023,\n'
    '  "exam": "UPSC Prelims",\n'
    '  "questions": [\n'
    '    {\n'
    '      "id": 1,\n'
    '      "year": 2023,\n'
    '      "exam": "UPSC Prelims",\n'
    '      "english": {\n'
    '        "question": "English question text here?",\n'
    '        "options": {"A": "...", "B": "...", "C": "...", "D": "..."}\n'
    '      },\n'
    '      "hindi": {\n'
    '        "question": "Hindi question text here?",\n'
    '        "options": {"A": "...", "B": "...", "C": "...", "D": "..."}\n'
    '      },\n'
    '      "answer": null\n'
    '    }\n'
    '  ]\n'
    '}\n\n'
    'Rules:\n'
    '- Every question MUST have exactly 4 options (A, B, C, D) in each language section.\n'
    '- If only one language is present, set the other language field to null.\n'
    '- answer must be one of: A, B, C, D (use null if not present in text).\n'
    '- Keep question text verbatim from the source.\n'
    '- If year/exam cannot be determined, use null.\n'
    '- Return ONLY the JSON object, nothing else.\n'
)


class DriveAIProvider:
    def __init__(self) -> None:
        if not settings.ai_configured:
            raise AIProviderNotConfiguredError()
        self._endpoint = settings.PCS2.rstrip('/')
        self._api_key = settings.PCS2_API
        self._model = settings.AI_MODEL_DEPLOYMENT
        self._client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                'Authorization': f'Bearer {self._api_key}',
                'Content-Type': 'application/json',
            },
        )

    async def extract_questions(self, ocr_text: str, chunk_index: int = 0) -> Dict[str, Any]:
        url = f'{self._endpoint}?api-version=2024-05-01-preview'
        user_prompt = (
            'Extract all MCQ questions from the following text. '
            'Return ONLY valid JSON as specified.\n\n'
            f'Text:\n{ocr_text}'
        )
        payload = {
            'model': self._model,
            'messages': [
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': 8000,
            'temperature': 0.1,
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
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)
        content = content.strip()
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                logger.warning('blob_ai.no_json_found', chunk_index=chunk_index)
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

            english = q.get('english')
            hindi = q.get('hindi')

            # Validate english section if present
            if english is not None:
                opts = english.get('options', {})
                if not isinstance(opts, dict) or not all(k in opts for k in ('A', 'B', 'C', 'D')):
                    english = None

            # Validate hindi section if present
            if hindi is not None:
                opts = hindi.get('options', {})
                if not isinstance(opts, dict) or not all(k in opts for k in ('A', 'B', 'C', 'D')):
                    hindi = None

            if english is None and hindi is None:
                continue

            answer = q.get('answer')
            if answer is not None:
                answer = str(answer).upper()
                if answer not in {'A', 'B', 'C', 'D'}:
                    answer = None

            validated.append({
                'id': q.get('id', idx),
                'year': q.get('year') or result.get('year'),
                'exam': q.get('exam') or result.get('exam') or '',
                'english': {
                    'question': str(english['question']).strip(),
                    'options': {
                        'A': str(english['options']['A']).strip(),
                        'B': str(english['options']['B']).strip(),
                        'C': str(english['options']['C']).strip(),
                        'D': str(english['options']['D']).strip(),
                    },
                } if english else None,
                'hindi': {
                    'question': str(hindi['question']).strip(),
                    'options': {
                        'A': str(hindi['options']['A']).strip(),
                        'B': str(hindi['options']['B']).strip(),
                        'C': str(hindi['options']['C']).strip(),
                        'D': str(hindi['options']['D']).strip(),
                    },
                } if hindi else None,
                'answer': answer,
            })

        logger.info('blob_ai.questions_parsed', count=len(validated), chunk_index=chunk_index)
        return {
            'document_type': result.get('document_type', 'Other'),
            'year': result.get('year'),
            'exam': result.get('exam', ''),
            'questions': validated,
        }

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {'document_type': 'Other', 'year': None, 'exam': '', 'questions': []}

    async def close(self) -> None:
        await self._client.aclose()
