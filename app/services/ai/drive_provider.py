import json
import re
import time
import traceback
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

_OPTION_KEY_MAP = {
    'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D',
    '1': 'A', '2': 'B', '3': 'C', '4': 'D',
    'optiona': 'A', 'optionb': 'B', 'optionc': 'C', 'optiond': 'D',
}


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
        logger.info(
            'blob_ai.sending_request',
            chunk_index=chunk_index,
            ocr_text_length=len(ocr_text),
            ocr_text_preview=ocr_text[:500],
        )
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
            logger.info('blob_ai.RAW_AI_RESPONSE', chunk_index=chunk_index, raw_response=content)
            return self._parse_response(content, chunk_index)
        except httpx.HTTPStatusError as e:
            logger.error('blob_ai.http_error', status=e.response.status_code, chunk_index=chunk_index, body=e.response.text[:500])
            raise AIProviderError(f'HTTP {e.response.status_code}: {e.response.text[:200]}', provider='azure')
        except httpx.RequestError as e:
            logger.error('blob_ai.request_error', error=str(e), chunk_index=chunk_index)
            raise AIProviderError(f'Request failed: {str(e)}', provider='azure')
        except (KeyError, IndexError) as e:
            logger.error('blob_ai.parse_error', error=str(e), traceback=traceback.format_exc())
            raise AIProviderError(f'Unexpected response structure: {str(e)}', provider='azure')

    def _parse_response(self, content: str, chunk_index: int) -> Dict[str, Any]:
        content_cleaned = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
        content_cleaned = re.sub(r'\s*```$', '', content_cleaned, flags=re.MULTILINE)
        content_cleaned = content_cleaned.strip()

        result = None
        parse_error = None

        try:
            result = json.loads(content_cleaned)
        except json.JSONDecodeError as e1:
            parse_error = str(e1)
            logger.warning('blob_ai.direct_parse_failed', chunk_index=chunk_index, error=str(e1), preview=content_cleaned[:300])
            match = re.search(r'\{.*\}', content_cleaned, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                    logger.info('blob_ai.extracted_json_via_regex', chunk_index=chunk_index)
                except json.JSONDecodeError as e2:
                    parse_error = str(e2)
                    logger.error(
                        'blob_ai.json_decode_error_final',
                        chunk_index=chunk_index,
                        error=str(e2),
                        raw_content=content[:2000],
                    )
                    return self._empty_result('JSON decode failed after regex extraction: ' + str(e2))
            else:
                logger.error(
                    'blob_ai.no_json_object_found',
                    chunk_index=chunk_index,
                    raw_content=content[:2000],
                )
                return self._empty_result('No JSON object found in AI response. Raw: ' + content[:500])

        if result is None:
            logger.error('blob_ai.result_is_none', chunk_index=chunk_index, parse_error=parse_error)
            return self._empty_result('Parse result is None')

        if not isinstance(result, dict):
            logger.error('blob_ai.result_not_dict', chunk_index=chunk_index, result_type=type(result).__name__, preview=str(result)[:200])
            return self._empty_result(f'Expected dict, got {type(result).__name__}')

        raw_questions = result.get('questions', [])
        if not isinstance(raw_questions, list):
            logger.error('blob_ai.questions_not_list', chunk_index=chunk_index, questions_type=type(raw_questions).__name__)
            return self._empty_result('questions field is not a list')

        logger.info('blob_ai.raw_question_count', chunk_index=chunk_index, count=len(raw_questions))

        validated: List[Dict[str, Any]] = []
        rejected_count = 0
        for idx, q in enumerate(raw_questions, start=1):
            if not isinstance(q, dict):
                logger.warning('blob_ai.question_not_dict', chunk_index=chunk_index, idx=idx, q_type=type(q).__name__)
                rejected_count += 1
                continue

            english = self._validate_lang_section(q.get('english'), f'Q{idx} english', chunk_index)
            hindi = self._validate_lang_section(q.get('hindi'), f'Q{idx} hindi', chunk_index)

            if english is None and hindi is None:
                logger.warning(
                    'blob_ai.question_rejected_both_null',
                    chunk_index=chunk_index,
                    idx=idx,
                    reason='Both english and hindi sections are null or invalid',
                    q_preview=str(q)[:300],
                )
                rejected_count += 1
                continue

            answer = q.get('answer')
            if answer is not None:
                answer = str(answer).upper().strip()
                if answer not in {'A', 'B', 'C', 'D'}:
                    logger.warning('blob_ai.invalid_answer_normalized', chunk_index=chunk_index, idx=idx, original_answer=answer)
                    answer = None

            validated.append({
                'id': q.get('id', idx),
                'year': q.get('year') or result.get('year'),
                'exam': q.get('exam') or result.get('exam') or '',
                'english': english,
                'hindi': hindi,
                'answer': answer,
            })

        document_type = result.get('document_type')
        if not document_type:
            logger.warning('blob_ai.document_type_missing', chunk_index=chunk_index)
            document_type = 'Other'
        else:
            logger.info('blob_ai.document_type_detected', chunk_index=chunk_index, document_type=document_type)

        logger.info(
            'blob_ai.questions_parsed',
            chunk_index=chunk_index,
            total_raw=len(raw_questions),
            accepted=len(validated),
            rejected=rejected_count,
            document_type=document_type,
            year=result.get('year'),
            exam=result.get('exam', ''),
        )

        return {
            'document_type': document_type,
            'year': result.get('year'),
            'exam': result.get('exam', ''),
            'questions': validated,
        }

    def _validate_lang_section(self, section: Any, label: str, chunk_index: int) -> Any:
        if section is None:
            return None
        if not isinstance(section, dict):
            logger.warning('blob_ai.lang_section_not_dict', label=label, chunk_index=chunk_index, section_type=type(section).__name__)
            return None

        question = section.get('question', '').strip()
        if not question:
            logger.warning('blob_ai.lang_section_empty_question', label=label, chunk_index=chunk_index, section_preview=str(section)[:200])
            return None

        opts = section.get('options', {})
        if not isinstance(opts, dict):
            logger.warning('blob_ai.lang_section_options_not_dict', label=label, chunk_index=chunk_index, opts_type=type(opts).__name__)
            return None

        if isinstance(opts, list):
            if len(opts) >= 4:
                opts = {'A': str(opts[0]), 'B': str(opts[1]), 'C': str(opts[2]), 'D': str(opts[3])}
                logger.info('blob_ai.options_normalized_from_list', label=label, chunk_index=chunk_index)
            else:
                logger.warning('blob_ai.options_list_too_short', label=label, chunk_index=chunk_index, length=len(opts))
                return None

        normalized: Dict[str, str] = {}
        for k, v in opts.items():
            mapped_key = _OPTION_KEY_MAP.get(str(k).lower(), str(k).upper())
            normalized[mapped_key] = str(v).strip()

        missing = [k for k in ('A', 'B', 'C', 'D') if k not in normalized]
        if missing:
            logger.warning(
                'blob_ai.lang_section_missing_options',
                label=label,
                chunk_index=chunk_index,
                missing_keys=missing,
                available_keys=list(normalized.keys()),
                question_preview=question[:100],
            )
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
    def _empty_result(reason: str = '') -> Dict[str, Any]:
        if reason:
            logger.error('blob_ai.empty_result_returned', reason=reason)
        return {'document_type': 'Other', 'year': None, 'exam': '', 'questions': []}

    async def close(self) -> None:
        await self._client.aclose()
