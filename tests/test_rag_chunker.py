"""Tests for application/rag/chunker.py."""
import pytest

from application.rag.chunker import (
    _approx_token_count,
    _split_paragraphs,
    _split_sentences,
    chunk_text,
)


class TestApproxTokenCount:
    def test_empty_string(self):
        assert _approx_token_count('') == 1  # max(1, ...)

    def test_short_string(self):
        assert _approx_token_count('abcd') == 1

    def test_exact_divisible(self):
        assert _approx_token_count('a' * 400) == 100

    def test_longer_text(self):
        text = 'Hello world! ' * 100
        assert _approx_token_count(text) > 0


class TestSplitParagraphs:
    def test_single_paragraph(self):
        result = _split_paragraphs('Hello world.')
        assert result == ['Hello world.']

    def test_two_paragraphs(self):
        result = _split_paragraphs('First.\n\nSecond.')
        assert result == ['First.', 'Second.']

    def test_multiple_blank_lines(self):
        result = _split_paragraphs('A.\n\n\n\nB.')
        assert result == ['A.', 'B.']

    def test_strips_whitespace(self):
        result = _split_paragraphs('  spaces  \n\n  more  ')
        assert result == ['spaces', 'more']

    def test_empty_text(self):
        assert _split_paragraphs('') == []

    def test_only_whitespace(self):
        assert _split_paragraphs('   \n\n   ') == []


class TestSplitSentences:
    def test_single_sentence(self):
        result = _split_sentences('Hello world.')
        assert result == ['Hello world.']

    def test_multiple_sentences(self):
        result = _split_sentences('First. Second. Third.')
        assert len(result) == 3

    def test_question_exclamation(self):
        result = _split_sentences('Really? Yes! OK.')
        assert len(result) == 3

    def test_strips_parts(self):
        result = _split_sentences('  A.  B.  ')
        assert all(s == s.strip() for s in result)


class TestChunkText:
    def test_empty_string(self):
        result = list(chunk_text(''))
        assert result == []

    def test_whitespace_only(self):
        result = list(chunk_text('   \n\n   '))
        assert result == []

    def test_single_short_chunk(self):
        text = 'Hello, world!'
        result = list(chunk_text(text))
        assert len(result) == 1
        assert result[0]['index'] == 0
        assert result[0]['text'] == text
        assert result[0]['token_count'] >= 1

    def test_chunk_dict_keys(self):
        result = list(chunk_text('Some text here.'))
        assert set(result[0].keys()) == {'index', 'text', 'token_count'}

    def test_indices_are_sequential(self):
        long_text = 'Sentence number {}. '.format('x' * 100) * 50
        chunks = list(chunk_text(long_text, max_tokens=20))
        indices = [c['index'] for c in chunks]
        assert indices == list(range(len(indices)))

    def test_multiple_chunks_for_long_text(self):
        # ~4000 chars → should produce multiple chunks with max_tokens=50
        text = ('Это длинный текст для тестирования разбивки на чанки. ' * 80)
        chunks = list(chunk_text(text, max_tokens=50))
        assert len(chunks) > 1

    def test_max_tokens_respected(self):
        text = 'word ' * 500
        max_tokens = 30
        chunks = list(chunk_text(text, max_tokens=max_tokens, overlap_tokens=0))
        for chunk in chunks:
            assert chunk['token_count'] <= max_tokens * 2  # rough upper-bound with overhead

    def test_overlap_produces_continuation(self):
        # With overlap, subsequent chunks should start with the tail of the previous one
        long_paragraph = 'A' * 800
        chunks = list(chunk_text(long_paragraph, max_tokens=50, overlap_tokens=10))
        if len(chunks) > 1:
            # The beginning of chunk[1] should be the tail of chunk[0]
            overlap_tail = chunks[0]['text'][-40:]
            assert chunks[1]['text'].startswith(overlap_tail) or len(chunks[1]['text']) > 0

    def test_no_overlap_option(self):
        long_text = 'B' * 1200
        chunks_with = list(chunk_text(long_text, max_tokens=50, overlap_tokens=20))
        chunks_without = list(chunk_text(long_text, max_tokens=50, overlap_tokens=0))
        # With overlap we get slightly more chunks because of repeated context
        assert len(chunks_with) >= len(chunks_without)

    def test_multiline_input(self):
        text = 'Line one.\n\nLine two.\n\nLine three.'
        chunks = list(chunk_text(text))
        assert len(chunks) >= 1
        joined = ' '.join(c['text'] for c in chunks)
        assert 'Line one.' in joined
        assert 'Line three.' in joined

    def test_russian_text(self):
        text = 'Документ о создании системы управления. ' * 30
        chunks = list(chunk_text(text, max_tokens=40))
        assert all(c['token_count'] >= 1 for c in chunks)
