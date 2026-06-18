import json
import re
import time
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.exceptions import AIProviderError, AIProviderNotConfiguredError
from app.core.logging import get_logger
from app.models.common import DocumentType
from app.services.ai.endpoint import build_chat_url, build_headers, _is_azure_openai

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
        self._url = build_chat_url(self._endpoint)
        self._is_azure_openai = _is_azure_openai(self._endpoint)
        self._client = httpx.AsyncClient(
            timeout=240.0,
            headers=build_headers(self._api_key),
        )
        logger.info('blob_ai.initialized', url=self._url, model=self._model)

    def _build_payload(self, system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
        payload = {
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': max_tokens,
            'temperature': 0.05,
            'top_p': 0.95,
        }
        # For Azure AI Foundry, model goes in the body; for Azure OpenAI it's in the URL
        if not self._is_azure_openai:
            payload['model'] = self._model
        return payload

    async def extract_questions(self, ocr_text: str, chunk_index: int = 0) -> Dict[str, Any]:
        user_prompt = (
            'Extract ALL numbered MCQ questions from the text below. '
            'Pair English and Hindi versions of the same question together. '
            'Return ONLY the JSON object — no markdown, no extra text.\n\n'
            f'TEXT:\n{ocr_text}'
        )
        payload = self._build_payload(_SYSTEM_PROMPT, user_prompt, max_tokens=12000)
        try:
            t0 = time.monotonic()
            response = await self._client.post(self._url, json=payload)
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
            logger.error('blob_ai.http_error', status=e.response.status_code, chunk_index=chunk_index, body=e.response.text[:300])
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
        normalized: Dict[str, str] = {k.upper(): str(v).strip() for k, v in opts.items()}
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
