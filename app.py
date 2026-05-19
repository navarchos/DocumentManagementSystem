import os
import secrets
import sys
from datetime import timedelta

import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=8)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

app.config['S3_BUCKET_NAME'] = os.environ.get('S3_BUCKET_NAME')
app.config['S3_ENDPOINT_URL'] = os.environ.get('S3_ENDPOINT_URL', 'https://storage.yandexcloud.net')
app.config['S3_REGION'] = os.environ.get('S3_REGION', 'ru-central1')
app.config['S3_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID')
app.config['S3_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY')

app.config['YANDEX_API_KEY'] = os.environ.get('YANDEX_API_KEY')
app.config['YANDEX_FOLDER_ID'] = os.environ.get('YANDEX_FOLDER_ID')
_folder_id = app.config['YANDEX_FOLDER_ID'] or ''
app.config['YANDEX_EMBED_DOC_URI'] = os.environ.get(
    'YANDEX_EMBED_DOC_URI', f'emb://{_folder_id}/text-search-doc/latest' if _folder_id else ''
)
app.config['YANDEX_EMBED_QUERY_URI'] = os.environ.get(
    'YANDEX_EMBED_QUERY_URI', f'emb://{_folder_id}/text-search-query/latest' if _folder_id else ''
)
app.config['YANDEX_LLM_URI'] = os.environ.get(
    'YANDEX_LLM_URI', f'gpt://{_folder_id}/yandexgpt-lite/latest' if _folder_id else ''
)
app.config['YANDEX_API_BASE'] = os.environ.get(
    'YANDEX_API_BASE', 'https://llm.api.cloud.yandex.net/foundationModels/v1'
)
app.config['RAG_EMBEDDING_DIM'] = int(os.environ.get('RAG_EMBEDDING_DIM', '256'))
app.config['RAG_TOP_K'] = int(os.environ.get('RAG_TOP_K', '6'))
app.config['RAG_CHUNK_TOKENS'] = int(os.environ.get('RAG_CHUNK_TOKENS', '800'))
app.config['RAG_CHUNK_OVERLAP'] = int(os.environ.get('RAG_CHUNK_OVERLAP', '100'))
app.config['RAG_MAX_PROMPT_CHARS'] = int(os.environ.get('RAG_MAX_PROMPT_CHARS', '20000'))
app.config['RAG_LLM_TEMPERATURE'] = float(os.environ.get('RAG_LLM_TEMPERATURE', '0.2'))
app.config['RAG_INDEX_CONCURRENCY'] = int(os.environ.get('RAG_INDEX_CONCURRENCY', '2'))

LOCAL_SQLITE_URI = 'sqlite:///edo_ldpr.db'


def get_database_uri():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return LOCAL_SQLITE_URI
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if not database_url.startswith('postgresql://'):
        return LOCAL_SQLITE_URI

    engine = create_engine(database_url, connect_args={'connect_timeout': 3})
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return database_url
    except SQLAlchemyError as error:
        print(f'PostgreSQL is unavailable, falling back to SQLite: {error}')
        return LOCAL_SQLITE_URI
    finally:
        engine.dispose()


app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Make `from app import app, db` resolve to this module when running `python app.py`.
sys.modules.setdefault('app', sys.modules[__name__])

# Imports below register models, context processors, and route decorators on app.
from application.database import seed_initial_data  # noqa: E402
import application.context  # noqa: E402,F401
import application.routes  # noqa: E402,F401


def is_rag_supported():
    """RAG requires PostgreSQL (pgvector) and a configured Yandex API key."""
    return (
        db.engine.dialect.name == 'postgresql'
        and bool(app.config.get('YANDEX_API_KEY'))
        and bool(app.config.get('YANDEX_FOLDER_ID'))
    )


app.is_rag_supported = is_rag_supported


with app.app_context():
    if db.engine.dialect.name == 'sqlite':
        db.create_all()
        seed_initial_data()


@app.cli.command('seed-db')
def seed_db():
    """Create the default departments and users after migrations are applied."""
    seed_initial_data()
    print('Initial data seeded.')


@app.cli.command('rag-reindex-all')
def rag_reindex_all_cmd():
    """Reindex every order (content, history, files) into the vector store."""
    from application.rag.indexer import reindex_all
    stats = reindex_all()
    print(
        f"Reindex done: documents={stats['documents']}, chunks={stats['chunks']}, "
        f"skipped={stats['skipped']}, errors={stats['errors']}"
    )


@app.cli.command('rag-reindex-order')
@click.argument('order_id')
def rag_reindex_order_cmd(order_id):
    """Reindex a single order by id."""
    from application.rag.indexer import reindex_order
    stats = reindex_order(order_id)
    print(
        f"Order {order_id}: documents={stats['documents']}, chunks={stats['chunks']}, "
        f"skipped={stats['skipped']}, errors={stats['errors']}"
    )


@app.cli.command('rag-test')
@click.option('--text', default='тестовый запрос', help='Текст для пробного эмбеддинга и completion')
def rag_test_cmd(text):
    """Smoke-test for Yandex API connectivity. Prints raw HTTP errors if any."""
    import httpx
    print('RAG_SUPPORTED:', app.is_rag_supported())
    print('YANDEX_FOLDER_ID:', app.config.get('YANDEX_FOLDER_ID'))
    print('YANDEX_API_KEY prefix:', (app.config.get('YANDEX_API_KEY') or '')[:8], '...')
    print('YANDEX_EMBED_QUERY_URI:', app.config.get('YANDEX_EMBED_QUERY_URI'))
    print('YANDEX_LLM_URI:', app.config.get('YANDEX_LLM_URI'))
    api_base = app.config['YANDEX_API_BASE'].rstrip('/')
    headers = {
        'Authorization': f"Api-Key {app.config['YANDEX_API_KEY']}",
        'x-folder-id': app.config['YANDEX_FOLDER_ID'],
        'Content-Type': 'application/json',
    }
    with httpx.Client(headers=headers, timeout=30.0) as cli:
        print('\n--- textEmbedding ---')
        resp = cli.post(
            f'{api_base}/textEmbedding',
            json={'modelUri': app.config['YANDEX_EMBED_QUERY_URI'], 'text': text},
        )
        print('status:', resp.status_code)
        body = resp.text
        print('body[:500]:', body[:500])
        if resp.status_code == 200:
            data = resp.json()
            emb = data.get('embedding') or []
            print('embedding length:', len(emb))

        print('\n--- completion ---')
        resp = cli.post(
            f'{api_base}/completion',
            json={
                'modelUri': app.config['YANDEX_LLM_URI'],
                'completionOptions': {'stream': False, 'temperature': 0.2, 'maxTokens': '200'},
                'messages': [
                    {'role': 'system', 'text': 'Отвечай одним словом'},
                    {'role': 'user', 'text': text},
                ],
            },
        )
        print('status:', resp.status_code)
        print('body[:500]:', resp.text[:500])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
