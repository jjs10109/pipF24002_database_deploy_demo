"""Flask app that lists class names from the students table."""

import csv
import os
import sqlite3
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
STUDENTS_CSV = BASE_DIR / "database" / "students.csv"
SQLITE_PATH = BASE_DIR / "instance" / "class.db"


def fetch_class_names():
    """Return student names, sorted, from Postgres or the local SQLite copy."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _names_from_postgres(database_url)
    return _names_from_sqlite()


def _names_from_postgres(database_url):
    import psycopg

    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://") :]

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students ORDER BY name")
            return [row[0] for row in cur.fetchall()]


def _names_from_sqlite():
    SQLITE_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as conn:
        _ensure_sqlite(conn)
        rows = conn.execute("SELECT name FROM students ORDER BY name").fetchall()
    return [row[0] for row in rows]


def _ensure_sqlite(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    existing = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if existing:
        return

    with STUDENTS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = [
            (int(row["id"]), row["name"].strip())
            for row in csv.DictReader(handle)
            if row["name"].strip()
        ]
    conn.executemany("INSERT INTO students (id, name) VALUES (?, ?)", rows)
    conn.commit()


@app.get("/")
def index():
    names = fetch_class_names()
    return render_template("index.html", names=names)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
