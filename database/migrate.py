"""Apply database/migrations/*.sql in order against DATABASE_URL.

Use this when pointing at Supabase (docker-compose runs migrations
automatically only on a fresh local volume).

    python database/migrate.py
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contractops")
url = url.replace("postgresql+psycopg2://", "postgresql://")

migrations = sorted((ROOT / "database" / "migrations").glob("*.sql"))
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS _migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())""")
for m in migrations:
    cur.execute("SELECT 1 FROM _migrations WHERE name = %s", (m.name,))
    if cur.fetchone():
        print(f"skip  {m.name} (already applied)")
        continue
    print(f"apply {m.name}")
    try:
        cur.execute(m.read_text(encoding="utf-8"))
        cur.execute("INSERT INTO _migrations (name) VALUES (%s)", (m.name,))
    except Exception as e:
        print(f"FAILED on {m.name}: {e}")
        sys.exit(1)
print("done.")
