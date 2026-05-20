"""Shared pytest fixtures for the Document Management System test suite.

The module configures a minimal Flask application backed by an in-memory
SQLite database so that every test starts from a clean, reproducible state
without touching the production database or any external services.
"""
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Point at a throw-away in-memory SQLite DB before any application code is
# imported; this prevents `get_database_uri()` from attempting a PostgreSQL
# connection during test collection.
# ---------------------------------------------------------------------------
os.environ.setdefault('DATABASE_URL', '')  # force SQLite fallback
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('TESTING', 'true')


@pytest.fixture(scope='session')
def app():
    """Create and configure the Flask application for the test session."""
    # Remove cached module so each test session starts fresh.
    for mod_name in list(sys.modules.keys()):
        if mod_name == 'app' or mod_name.startswith('application'):
            del sys.modules[mod_name]

    import app as app_module

    flask_app = app_module.app
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        WTF_CSRF_ENABLED=False,
        SECRET_KEY='test-secret-key',
        # Disable S3 for all unit tests
        S3_BUCKET_NAME=None,
        S3_ACCESS_KEY_ID=None,
        S3_SECRET_ACCESS_KEY=None,
    )

    with flask_app.app_context():
        from app import db as _db
        # Drop and recreate to guarantee the schema matches current models,
        # even if an existing file-based SQLite has a stale schema.
        _db.drop_all()
        _db.create_all()
        from application.database import seed_initial_data
        seed_initial_data()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='session')
def db(app):
    """Return the SQLAlchemy *db* object bound to the session-scoped app."""
    from app import db as _db
    return _db


@pytest.fixture()
def client(app):
    """Return a Flask test client with a fresh request context."""
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """Return a test client pre-authenticated as the seed admin user."""
    with client.session_transaction() as sess:
        sess['user_id'] = 'u-admin'
        sess['user_name'] = 'Администратор'
        sess['user_role'] = 'admin'
        sess['department_id'] = None
    return client


@pytest.fixture()
def runner(app):
    """Return a Flask CLI test runner."""
    return app.test_cli_runner()
