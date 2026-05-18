# Database setup

The application tries to use PostgreSQL first. Put the connection string into `.env`:

```text
DATABASE_URL=postgresql://edo_user:password@localhost:5432/edo_ldpr
```

You can also set it manually before starting Flask:

```powershell
$env:DATABASE_URL = "postgresql://edo_user:password@localhost:5432/edo_ldpr"
$env:FLASK_APP = "app.py"
```

If PostgreSQL is unavailable or `DATABASE_URL` is missing, the application falls
back to a local SQLite database at `instance\edo_ldpr.db`.

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Apply the database schema:

```powershell
.\.venv\Scripts\python.exe -m flask db upgrade
```

Migrations are needed for PostgreSQL. In SQLite fallback mode, the application
creates the local tables automatically on startup.

Seed default departments and demo users if the database is empty:

```powershell
.\.venv\Scripts\python.exe -m flask seed-db
```

Uploaded files are not stored in the database. Keep the `uploads` directory when
moving the application to another machine or server.
