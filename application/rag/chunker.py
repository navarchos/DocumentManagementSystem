"""Text splitter for RAG indexing.

The Yandex Foundation Models embedding models accept up to ~2048 tokens per call.
We approximate tokens as `len(text) / 4`; for Russian text that is conservative.
"""
import re
from typing import Iterator


def _approx_token_count(text: str) -> int:
    return max(1, len(text) // 4)


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r'\n\s*\n', text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', paragraph)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, *, max_tokens: int = 800, overlap_tokens: int = 100) -> Iterator[dict]:
    """Yield ``{index, text, token_count}`` dicts.

    Strategy: paragraph-first, then sentence-level packing into ~max_tokens.
    A trailing overlap of ~overlap_tokens characters/4 is repeated at the start
    of the next chunk to preserve local context across boundaries.
    """
    if not text or not text.strip():
        return

    max_chars = max_tokens * 4
    overlap_chars = max(0, overlap_tokens) * 4

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        paragraphs = [text.strip()]

    buffer: list[str] = []
    buffer_len = 0
    chunk_index = 0

    def flush() -> dict | None:
        nonlocal chunk_index, buffer, buffer_len
        if not buffer:
            return None
        chunk_text_value = '\n'.join(buffer).strip()
        if not chunk_text_value:
            buffer = []
            buffer_len = 0
            return None
        result = {
            'index': chunk_index,
            'text': chunk_text_value,
            'token_count': _approx_token_count(chunk_text_value),
        }
        chunk_index += 1
        if overlap_chars and len(chunk_text_value) > overlap_chars:
            tail = chunk_text_value[-overlap_chars:]
            buffer = [tail]
            buffer_len = len(tail)
        else:
            buffer = []
            buffer_len = 0
        return result

    for paragraph in paragraphs:
        units = [paragraph] if len(paragraph) <= max_chars else _split_sentences(paragraph)
        for unit in units:
            if len(unit) > max_chars:
                # Hard-split overly long sentences/units by character window.
                for i in range(0, len(unit), max_chars):
                    piece = unit[i:i + max_chars]
                    if buffer_len + len(piece) + 1 > max_chars and buffer:
                        result = flush()
                        if result:
                            yield result
                    buffer.append(piece)
                    buffer_len += len(piece) + 1
                continue
            if buffer_len + len(unit) + 1 > max_chars and buffer:
                result = flush()
                if result:
                    yield result
            buffer.append(unit)
            buffer_len += len(unit) + 1

    result = flush()
    if result:
        yield result
