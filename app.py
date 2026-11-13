"""Flask app that shows project groups from the students table."""

import csv
import os
import sqlite3
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
# assignment_rules imports cluster_model from sys.path, not as a package.
MODEL_DIR = BASE_DIR / "model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from assignment_rules import SKILL_COLUMNS, assign_groups
from cluster_model import CENTROIDS

app = Flask(__name__)

STUDENTS_CSV = BASE_DIR / "database" / "students.csv"
SQLITE_PATH = BASE_DIR / "instance" / "class.db"
N_GROUPS = 8

_SQLITE_REQUIRED = {"id", "identifier", "name", *SKILL_COLUMNS}


def fetch_class_names():
    """Return student names, sorted, from Postgres or the local SQLite copy."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _names_from_postgres(database_url)
    return _names_from_sqlite()


def fetch_students():
    """Return identifier, name, and the four skill ratings for each student."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _students_from_postgres(database_url)
    return _students_from_sqlite()


def _normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://") :]
    return database_url


def _names_from_postgres(database_url):
    import psycopg

    with psycopg.connect(_normalize_database_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students ORDER BY name")
            return [row[0] for row in cur.fetchall()]


def _names_from_sqlite():
    SQLITE_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as conn:
        _ensure_sqlite(conn)
        rows = conn.execute("SELECT name FROM students ORDER BY name").fetchall()
    return [row[0] for row in rows]


def _students_from_postgres(database_url):
    import psycopg

    with psycopg.connect(_normalize_database_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT identifier, name, skill_programming, skill_data_stats,
                       skill_frontend_design, skill_business_pitch
                FROM students
                """
            )
            return [_student_from_row(row) for row in cur.fetchall()]


def _students_from_sqlite():
    SQLITE_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as conn:
        _ensure_sqlite(conn)
        rows = conn.execute(
            """
            SELECT identifier, name, skill_programming, skill_data_stats,
                   skill_frontend_design, skill_business_pitch
            FROM students
            """
        ).fetchall()
    return [_student_from_row(row) for row in rows]


def _student_from_row(row):
    identifier, name, *skills = row
    return student_record(identifier, name, *skills)


def student_record(identifier, name, *skills):
    """Map one student to the fields the page and assign_groups share.

    id is the identifier string (netid, email, or N-number). Grouping sorts
    that string and does not use the integer primary key.
    """
    if len(skills) != len(SKILL_COLUMNS):
        raise ValueError(
            f"expected {len(SKILL_COLUMNS)} skill ratings, got {len(skills)}"
        )
    record = {
        "id": str(identifier).strip(),
        "name": str(name).strip(),
    }
    for column, value in zip(SKILL_COLUMNS, skills):
        record[column] = int(value)
    return record


def grouping_input(student):
    """Return the dict assign_groups expects: id plus the four skill ratings."""
    payload = {"id": student["id"]}
    for column in SKILL_COLUMNS:
        payload[column] = int(student[column])
    return payload


def _sqlite_columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(students)")}


def _ensure_sqlite(conn):
    columns = _sqlite_columns(conn)
    if columns and not _SQLITE_REQUIRED.issubset(columns):
        # Older local files only stored id and name. CREATE TABLE IF NOT EXISTS
        # would keep that table, so replace it and reload skills from the CSV.
        conn.execute("DROP TABLE students")
        columns = set()
    if not columns:
        conn.execute(
            """
            CREATE TABLE students (
                id INTEGER PRIMARY KEY,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                skill_programming INTEGER NOT NULL,
                skill_data_stats INTEGER NOT NULL,
                skill_frontend_design INTEGER NOT NULL,
                skill_business_pitch INTEGER NOT NULL
            )
            """
        )

    existing = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if existing:
        return

    rows = []
    with STUDENTS_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["name"].strip()
            if not name:
                continue
            record = student_record(
                row["identifier"],
                name,
                row["skill_programming"],
                row["skill_data_stats"],
                row["skill_frontend_design"],
                row["skill_business_pitch"],
            )
            rows.append(
                (
                    int(row["id"]),
                    record["id"],
                    record["name"],
                    *(record[column] for column in SKILL_COLUMNS),
                )
            )
    conn.executemany(
        """
        INSERT INTO students (
            id, identifier, name, skill_programming, skill_data_stats,
            skill_frontend_design, skill_business_pitch
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def build_group_page(students):
    """Assign groups, then join each result back to the student's name."""
    if not students:
        return [], 0

    names = {student["id"]: student["name"] for student in students}
    assignments = assign_groups([grouping_input(student) for student in students])
    return _present_groups(assignments, names)


def build_groups_api(students, n_groups=N_GROUPS):
    """JSON for GET /api/groups. Members are names only; clusters are counts."""
    assignments = assign_groups(
        [grouping_input(student) for student in students],
        n_groups=n_groups,
    )
    names = {student["id"]: student["name"] for student in students}
    labels = sorted({item["cluster"] for item in assignments})
    sizes = {label: 0 for label in labels}
    for item in assignments:
        sizes[item["cluster"]] += 1

    groups = []
    missing = 0
    for number in range(1, n_groups + 1):
        members = [item for item in assignments if item["group"] == number]
        counts = {label: 0 for label in labels}
        for item in members:
            counts[item["cluster"]] += 1
        if any(count == 0 for count in counts.values()):
            missing += 1
        groups.append(
            {
                "group": number,
                "members": [
                    names[item["id"]]
                    for item in sorted(members, key=lambda item: names[item["id"]])
                ],
                "cluster_counts": {str(label): counts[label] for label in labels},
            }
        )

    return {
        "n_groups": n_groups,
        "groups": groups,
        "clusters": [
            {
                "cluster": label,
                "students": sizes[label],
                "centroid": list(CENTROIDS[label]),
            }
            for label in labels
        ],
        "groups_missing_a_cluster": missing,
    }


def _present_groups(assignments, names, n_groups=8):
    clusters = sorted({item["cluster"] for item in assignments})
    groups = []
    missing = 0
    for number in range(1, n_groups + 1):
        members = [item for item in assignments if item["group"] == number]
        counts = {cluster: 0 for cluster in clusters}
        for item in members:
            counts[item["cluster"]] += 1
        if any(count == 0 for count in counts.values()):
            missing += 1
        groups.append(
            {
                "number": number,
                "count": len(members),
                "cluster_counts": [
                    {"cluster": cluster, "count": counts[cluster]}
                    for cluster in clusters
                ],
                "members": [
                    {"name": names[item["id"]], "cluster": item["cluster"]}
                    for item in sorted(members, key=lambda item: names[item["id"]])
                ],
            }
        )
    return groups, missing


@app.get("/")
def index():
    students = fetch_students()
    groups, missing_groups = build_group_page(students)
    return render_template(
        "index.html",
        student_count=len(students),
        groups=groups,
        missing_groups=missing_groups,
    )


@app.get("/api/groups")
def api_groups():
    return jsonify(build_groups_api(fetch_students()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
