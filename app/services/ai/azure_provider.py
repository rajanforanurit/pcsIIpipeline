import json
import re
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.exceptions import AIProviderError, AIProviderNotConfiguredError
from app.core.logging import get_logger
from app.services.ai.base_provider import BaseAIProvider
from app.services.ai.endpoint import build_chat_url, build_headers, _is_azure_openai

logger = get_logger(__name__)

_WORD_COUNT_BUCKETS = [(200, 5), (500, 10), (1000, 15), (2000, 20), (3000, 30)]
_MIN_QUESTIONS = 5


def _estimate_question_count(chunk: str) -> int | None:
    word_count = len(chunk.split())
    for threshold, count in _WORD_COUNT_BUCKETS:
        if word_count <= threshold:
            return count
    return None


def _build_system_prompt(suggested_count: int | None) -> str:
    if suggested_count is None:
        count_instruction = (
            f'Generate as many questions as the text can support. '
            f'There is NO upper limit — analyse the full content and create one question per distinct, '
            f'examinable fact or concept. Minimum {_MIN_QUESTIONS} questions.'
        )
    else:
        count_instruction = (
            f'Generate exactly {suggested_count} questions based on the text provided. '
            f'If the text cannot support {suggested_count} distinct questions, '
            f'generate as many as possible (minimum {_MIN_QUESTIONS}).'
        )
    return (
        'You are an expert UPSC/PSC exam question creator. '
        'Generate high-quality multiple choice questions from the provided text.\n'
        'Rules:\n'
        '- Each question must be factual and directly based on the provided text\n'
        '- Questions must be UPSC/PSC exam style\n'
        '- Each question must have exactly 4 options (A, B, C, D)\n'
        '- Only one option must be correct\n'
        '- correct_answer must be exactly one of: A, B, C, D\n'
        '- explanation must be concise (1-2 sentences)\n'
        '- Return ONLY valid JSON array, no markdown, no extra text\n'
        f'- {count_instruction}\n'
        'Output format (strict JSON array):\n'
        '[\n'
        '  {{\n'
        '    "question": "Question text here?",\n'
        '    "options": {{"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}},\n'
        '    "correct_answer": "A",\n'
        '    "explanation": "Brief explanation"\n'
        '  }}\n'
        ']'
    )


def _estimate_max_tokens(suggested_count: int | None) -> int:
    if suggested_count is None:
        return 8000
    return max(2000, int(suggested_count * 120 * 1.2))


class AzureAIProvider(BaseAIProvider):
    def __init__(self) -> None:
        if not settings.ai_configured:
            raise AIProviderNotConfiguredError()
        self._endpoint = settings.PCS2.rstrip('/')
        self._api_key = settings.PCS2_API
        self._model = settings.AI_MODEL_DEPLOYMENT
        self._url = build_chat_url(self._endpoint)
        self._is_azure_openai = _is_azure_openai(self._endpoint)
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers=build_headers(self._api_key),
        )
        logger.info('azure_ai.initialized', url=self._url, model=self._model)

    def _build_payload(self, system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
        payload = {
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': max_tokens,
            'temperature': 0.7,
            'top_p': 0.95,
        }
        if not self._is_azure_openai:
            payload['model'] = self._model
        return payload

    async def generate_questions(self, chunk: str, chunk_index: int, book_title: str, subject: str) -> List[Dict[str, Any]]:
        suggested_count = _estimate_question_count(chunk)
        system_prompt = _build_system_prompt(suggested_count)
        max_tokens = _estimate_max_tokens(suggested_count)
        logger.info(
            'ai.generating_questions',
            chunk_index=chunk_index,
            word_count=len(chunk.split()),
            suggested_count=suggested_count if suggested_count else 'auto',
            max_tokens=max_tokens,
        )
        count_hint = (
            f'Generate {suggested_count} UPSC/PSC style MCQ questions'
            if suggested_count
            else 'Generate as many UPSC/PSC style MCQ questions as the text supports (no upper limit)'
        )
        user_prompt = f'Book: {book_title}\nSubject: {subject}\n\nText:\n{chunk}\n\n{count_hint}. Return only JSON array.'
        payload = self._build_payload(system_prompt, user_prompt, max_tokens)
        try:
            response = await self._client.post(self._url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            logger.info('ai.response_received', chunk_index=chunk_index, tokens=data.get('usage', {}).get('total_tokens', 0))
            return self._parse_response(content, chunk_index)
        except httpx.HTTPStatusError as e:
            logger.error('ai.http_error', status=e.response.status_code, chunk_index=chunk_index, body=e.response.text[:300])
            raise AIProviderError(f'HTTP {e.response.status_code}: {e.response.text[:200]}', provider='azure')
        except httpx.RequestError as e:
            logger.error('ai.request_error', error=str(e), chunk_index=chunk_index)
            raise AIProviderError(f'Request failed: {str(e)}', provider='azure')
        except (KeyError, IndexError) as e:
            logger.error('ai.parse_response_error', error=str(e))
            raise AIProviderError(f'Unexpected response structure: {str(e)}', provider='azure')

    def _parse_response(self, content: str, chunk_index: int) -> List[Dict[str, Any]]:
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            logger.warning('ai.no_json_array_found', chunk_index=chunk_index)
            return []
        try:
            questions = json.loads(json_match.group())
            validated: List[Dict[str, Any]] = []
            for q in questions:
                if not all(k in q for k in ('question', 'options', 'correct_answer')):
                    continue
                opts = q.get('options', {})
                if not all(k in opts for k in ('A', 'B', 'C', 'D')):
                    continue
                if q['correct_answer'].upper() not in {'A', 'B', 'C', 'D'}:
                    continue
                validated.append({
                    'question': str(q['question']).strip(),
                    'options': {
                        'A': str(opts['A']).strip(),
                        'B': str(opts['B']).strip(),
                        'C': str(opts['C']).strip(),
                        'D': str(opts['D']).strip(),
                    },
                    'correct_answer': q['correct_answer'].upper(),
                    'explanation': str(q.get('explanation', '')).strip(),
                    'chunk_index': chunk_index,
                })
            logger.info('ai.questions_parsed', count=len(validated), chunk_index=chunk_index)
            return validated
        except json.JSONDecodeError as e:
            logger.error('ai.json_decode_error', error=str(e), chunk_index=chunk_index)
            return []

    async def health_check(self) -> bool:
        try:
            payload = self._build_payload('ping', 'ping', max_tokens=5)
            resp = await self._client.post(self._url, json=payload)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
