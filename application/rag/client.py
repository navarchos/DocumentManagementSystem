"""HTTP client for the Yandex Foundation Models API (embeddings and completions)."""
import threading
import time
from typing import Iterable, Sequence

import httpx
from flask import current_app
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class YandexAPIError(RuntimeError):
    """Raised when the Yandex Foundation Models API returns an error."""


class _RateLimiter:
    """Simple thread-safe minimum-interval limiter."""

    def __init__(self, min_interval_s: float = 0.0):
        self._min_interval_s = min_interval_s
        self._last = 0.0
        self._lock = threading.Lock()

    def acquire(self):
        if self._min_interval_s <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval_s - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


_embed_limiter = _RateLimiter(min_interval_s=0.1)
_complete_limiter = _RateLimiter(min_interval_s=0.2)


def _retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


def _headers() -> dict:
    api_key = current_app.config.get('YANDEX_API_KEY')
    folder_id = current_app.config.get('YANDEX_FOLDER_ID')
    if not api_key or not folder_id:
        raise YandexAPIError('Yandex API key or folder id is not configured')
    return {
        'Authorization': f'Api-Key {api_key}',
        'x-folder-id': folder_id,
        'Content-Type': 'application/json',
    }


def _base_url() -> str:
    return current_app.config['YANDEX_API_BASE'].rstrip('/')


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _post(client: httpx.Client, url: str, payload: dict) -> dict:
    resp = client.post(url, json=payload)
    if resp.status_code >= 400:
        # Trigger retry for 429/5xx, otherwise convert to YandexAPIError.
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _retryable_exception(exc):
                raise
            raise YandexAPIError(
                f'Yandex API error {resp.status_code}: {resp.text[:500]}'
            ) from exc
    return resp.json()


def _embed_one(text: str, model_uri: str) -> list[float]:
    _embed_limiter.acquire()
    url = f'{_base_url()}/textEmbedding'
    payload = {'modelUri': model_uri, 'text': text}
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    with httpx.Client(headers=_headers(), timeout=timeout) as client:
        data = _post(client, url, payload)
    embedding = data.get('embedding')
    if not isinstance(embedding, list):
        raise YandexAPIError(f'Unexpected embedding response: {data}')
    return [float(x) for x in embedding]


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Embed a batch of documents using the doc-side embedding model."""
    model_uri = current_app.config['YANDEX_EMBED_DOC_URI']
    if not model_uri:
        raise YandexAPIError('YANDEX_EMBED_DOC_URI is not configured')
    return [_embed_one(t, model_uri) for t in texts]


def embed_query(text: str) -> list[float]:
    """Embed a single user query using the query-side embedding model."""
    model_uri = current_app.config['YANDEX_EMBED_QUERY_URI']
    if not model_uri:
        raise YandexAPIError('YANDEX_EMBED_QUERY_URI is not configured')
    return _embed_one(text, model_uri)


def complete(
    messages: Iterable[dict],
    *,
    temperature: float | None = None,
    max_tokens: int = 2000,
    model_uri: str | None = None,
) -> str:
    """Run a chat completion against YandexGPT.

    messages is a list of dicts with keys role ('system'|'user'|'assistant') and text.
    """
    _complete_limiter.acquire()
    model = model_uri or current_app.config['YANDEX_LLM_URI']
    if not model:
        raise YandexAPIError('YANDEX_LLM_URI is not configured')
    temp = temperature if temperature is not None else current_app.config['RAG_LLM_TEMPERATURE']
    payload = {
        'modelUri': model,
        'completionOptions': {
            'stream': False,
            'temperature': float(temp),
            'maxTokens': str(max_tokens),
        },
        'messages': [
            {'role': m['role'], 'text': m['text']} for m in messages
        ],
    }
    url = f'{_base_url()}/completion'
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
    with httpx.Client(headers=_headers(), timeout=timeout) as client:
        data = _post(client, url, payload)
    try:
        return data['result']['alternatives'][0]['message']['text']
    except (KeyError, IndexError, TypeError) as exc:
        raise YandexAPIError(f'Unexpected completion response: {data}') from exc
