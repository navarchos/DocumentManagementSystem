"""Tests for application/file_utils.py."""
import pytest


class TestAllowedFile:
    """allowed_file() should accept only whitelisted extensions."""

    def test_allowed_extensions(self):
        from application.file_utils import allowed_file
        for ext in ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png', 'zip'):
            assert allowed_file(f'file.{ext}'), f'{ext} should be allowed'

    def test_disallowed_extensions(self):
        from application.file_utils import allowed_file
        for ext in ('exe', 'sh', 'bat', 'py', 'js', 'html', 'php'):
            assert not allowed_file(f'file.{ext}'), f'{ext} should be disallowed'

    def test_no_extension(self):
        from application.file_utils import allowed_file
        assert not allowed_file('noextension')

    def test_case_insensitive(self):
        from application.file_utils import allowed_file
        assert allowed_file('report.PDF')
        assert allowed_file('image.PNG')
        assert allowed_file('sheet.XLSX')

    def test_dot_only(self):
        from application.file_utils import allowed_file
        assert not allowed_file('.')

    def test_multiple_dots(self):
        from application.file_utils import allowed_file
        assert allowed_file('archive.tar.gz') is False  # gz not whitelisted
        assert allowed_file('report.final.pdf')         # last part is pdf


class TestBuildStoragePath:
    def test_basic(self):
        from application.file_utils import build_storage_path
        assert build_storage_path('ord-1', 'file.pdf') == 'orders/ord-1/file.pdf'

    def test_special_chars_in_order_id(self):
        from application.file_utils import build_storage_path
        result = build_storage_path('ord-abc-123', 'my_doc.docx')
        assert result == 'orders/ord-abc-123/my_doc.docx'


class TestIsS3StoragePath:
    def test_s3_path(self):
        from application.file_utils import is_s3_storage_path
        assert is_s3_storage_path('orders/ord-1/doc.pdf') is True

    def test_local_path(self):
        from application.file_utils import is_s3_storage_path
        assert is_s3_storage_path('/var/uploads/doc.pdf') is False
        assert is_s3_storage_path('uploads/doc.pdf') is False

    def test_empty_path(self):
        from application.file_utils import is_s3_storage_path
        assert is_s3_storage_path('') is False


class TestIsS3StorageEnabled:
    def test_disabled_when_no_config(self, app):
        with app.app_context():
            from application.file_utils import is_s3_storage_enabled
            # conftest sets S3_BUCKET_NAME=None
            assert is_s3_storage_enabled() is False

    def test_enabled_when_all_set(self, app):
        with app.app_context():
            from flask import current_app
            from application.file_utils import is_s3_storage_enabled
            original = {
                'S3_BUCKET_NAME': current_app.config.get('S3_BUCKET_NAME'),
                'S3_ACCESS_KEY_ID': current_app.config.get('S3_ACCESS_KEY_ID'),
                'S3_SECRET_ACCESS_KEY': current_app.config.get('S3_SECRET_ACCESS_KEY'),
            }
            current_app.config['S3_BUCKET_NAME'] = 'my-bucket'
            current_app.config['S3_ACCESS_KEY_ID'] = 'AKID'
            current_app.config['S3_SECRET_ACCESS_KEY'] = 'secret'
            assert is_s3_storage_enabled() is True
            # Restore
            for k, v in original.items():
                current_app.config[k] = v

    def test_partially_missing(self, app):
        with app.app_context():
            from flask import current_app
            from application.file_utils import is_s3_storage_enabled
            current_app.config['S3_BUCKET_NAME'] = 'my-bucket'
            current_app.config['S3_ACCESS_KEY_ID'] = None
            current_app.config['S3_SECRET_ACCESS_KEY'] = None
            assert is_s3_storage_enabled() is False
            current_app.config['S3_BUCKET_NAME'] = None
