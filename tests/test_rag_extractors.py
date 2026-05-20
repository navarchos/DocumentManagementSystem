"""Tests for application/rag/extractors.py.

We test the pure text-extraction helpers independently of S3 and the database.
"""
import io
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers – lightweight fakes
# ---------------------------------------------------------------------------

def make_order(**kwargs):
    defaults = dict(
        title='Test Order',
        priority='Нормальный',
        status='Черновик',
        creator_name='Admin',
        deadline=None,
        content=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_history_entry(action='Создано', user_name='Admin', details='', created_at=None):
    return SimpleNamespace(
        action=action,
        user_name=user_name,
        details=details,
        created_at=created_at or datetime(2025, 1, 15, 10, 0, 0),
    )


def make_order_file(original_name='doc.pdf', filename='doc.pdf', filepath='orders/ord-1/doc.pdf'):
    return SimpleNamespace(
        id=1,
        original_name=original_name,
        filename=filename,
        filepath=filepath,
    )


# ---------------------------------------------------------------------------
# extract_order_content
# ---------------------------------------------------------------------------

class TestExtractOrderContent:
    def test_all_fields(self):
        from application.rag.extractors import extract_order_content
        order = make_order(
            title='My Order',
            priority='Высокий',
            status='В работе',
            creator_name='Alice',
            deadline=date(2025, 12, 31),
            content='Some body text.',
        )
        text = extract_order_content(order)
        assert 'My Order' in text
        assert 'Высокий' in text
        assert 'В работе' in text
        assert 'Alice' in text
        assert '2025-12-31' in text
        assert 'Some body text.' in text

    def test_no_content_or_deadline(self):
        from application.rag.extractors import extract_order_content
        order = make_order(title='Simple', priority='Нормальный', status='Черновик',
                           creator_name='Bob', deadline=None, content=None)
        text = extract_order_content(order)
        assert text is not None
        assert 'Simple' in text

    def test_empty_order_returns_none(self):
        from application.rag.extractors import extract_order_content
        order = make_order(title=None, priority=None, status=None,
                           creator_name=None, deadline=None, content=None)
        assert extract_order_content(order) is None

    def test_title_label(self):
        from application.rag.extractors import extract_order_content
        order = make_order(title='Report Q1')
        text = extract_order_content(order)
        assert 'Заголовок: Report Q1' in text


# ---------------------------------------------------------------------------
# extract_order_history
# ---------------------------------------------------------------------------

class TestExtractOrderHistory:
    def test_basic_history(self):
        from application.rag.extractors import extract_order_history
        entries = [
            make_history_entry('Создано', 'Alice', 'Initial'),
            make_history_entry('Утверждено', 'Bob', 'Approved by manager'),
        ]
        text = extract_order_history(entries)
        assert 'Создано' in text
        assert 'Alice' in text
        assert 'Утверждено' in text
        assert 'Approved by manager' in text

    def test_empty_history_returns_none(self):
        from application.rag.extractors import extract_order_history
        assert extract_order_history([]) is None

    def test_with_dict_result(self):
        from application.rag.extractors import extract_order_history
        entries = [make_history_entry()]
        text = extract_order_history(entries, order_result={'content': 'Done successfully.'})
        assert 'Done successfully.' in text
        assert 'Результат исполнения' in text

    def test_with_non_dict_result(self):
        from application.rag.extractors import extract_order_history
        entries = [make_history_entry()]
        text = extract_order_history(entries, order_result='simple string result')
        assert 'Результат исполнения' in text

    def test_result_without_content_key(self):
        from application.rag.extractors import extract_order_history
        entries = [make_history_entry()]
        text = extract_order_history(entries, order_result={'other_key': 'value'})
        # 'Результат исполнения' should NOT appear – no 'content' key
        assert 'Результат исполнения' not in text


# ---------------------------------------------------------------------------
# _extract_txt
# ---------------------------------------------------------------------------

class TestExtractTxt:
    def test_utf8(self):
        from application.rag.extractors import _extract_txt
        data = 'Привет мир'.encode('utf-8')
        assert _extract_txt(data) == 'Привет мир'

    def test_cp1251(self):
        from application.rag.extractors import _extract_txt
        data = 'Привет мир'.encode('cp1251')
        assert _extract_txt(data) == 'Привет мир'

    def test_strips_whitespace(self):
        from application.rag.extractors import _extract_txt
        data = '  hello  '.encode('utf-8')
        assert _extract_txt(data) == 'hello'

    def test_empty_bytes(self):
        from application.rag.extractors import _extract_txt
        assert _extract_txt(b'') == ''


# ---------------------------------------------------------------------------
# _file_extension
# ---------------------------------------------------------------------------

class TestFileExtension:
    def test_pdf(self):
        from application.rag.extractors import _file_extension
        assert _file_extension('report.pdf') == 'pdf'

    def test_uppercase(self):
        from application.rag.extractors import _file_extension
        assert _file_extension('REPORT.PDF') == 'pdf'

    def test_no_extension(self):
        from application.rag.extractors import _file_extension
        assert _file_extension('README') == ''

    def test_multiple_dots(self):
        from application.rag.extractors import _file_extension
        assert _file_extension('archive.tar.gz') == 'gz'


# ---------------------------------------------------------------------------
# extract_file_text – unsupported extension should return None immediately
# ---------------------------------------------------------------------------

class TestExtractFileText:
    def test_unsupported_extension(self, app):
        from application.rag.extractors import extract_file_text
        order_file = make_order_file(original_name='image.jpg', filename='image.jpg')
        with app.app_context():
            result = extract_file_text(order_file)
        assert result is None

    def test_supported_extension_no_s3(self, app):
        """When S3 is not configured the function should return None gracefully."""
        from application.rag.extractors import extract_file_text
        order_file = make_order_file(original_name='doc.pdf', filepath='orders/ord-1/doc.pdf')
        with app.app_context():
            result = extract_file_text(order_file)
        # S3 is disabled in test config → _download_file_bytes returns None
        assert result is None
