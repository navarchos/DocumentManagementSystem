import os
import secrets
import sys
from datetime import timedelta

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv


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

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError('DATABASE_URL is required and must point to PostgreSQL.')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if not database_url.startswith('postgresql://'):
    raise RuntimeError('DATABASE_URL must use the postgresql:// scheme.')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Make `from app import app, db` resolve to this module when running `python app.py`.
sys.modules.setdefault('app', sys.modules[__name__])

# Imports below register models, context processors, and route decorators on app.
from application.database import seed_initial_data  # noqa: E402
import application.context  # noqa: E402,F401
import application.routes  # noqa: E402,F401


@app.cli.command('seed-db')
def seed_db():
    """Create the default departments and users after migrations are applied."""
    seed_initial_data()
    print('Initial data seeded.')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
