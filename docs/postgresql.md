# PostgreSQL setup

The application requires PostgreSQL. Put the connection string into `.env`:

```text
DATABASE_URL=postgresql://edo_user:password@localhost:5432/edo_ldpr
```

You can also set it manually before starting Flask:

```powershell
$env:DATABASE_URL = "postgresql://edo_user:password@localhost:5432/edo_ldpr"
$env:FLASK_APP = "app.py"
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Apply the database schema:

```powershell
.\.venv\Scripts\python.exe -m flask db upgrade
```

Seed default departments and demo users if the database is empty:

```powershell
.\.venv\Scripts\python.exe -m flask seed-db
```

Uploaded files are not stored in the database. Keep the `uploads` directory when
moving the application to another machine or server.
