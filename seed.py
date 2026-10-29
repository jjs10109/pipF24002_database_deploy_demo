"""Load student rows into Postgres when the table is still empty.

schema.sql creates the tables and does not insert students. Railway runs
this after that file, using DATABASE_URL from the Postgres service.
"""

import csv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STUDENTS_CSV = BASE_DIR / "database" / "students.csv"


def database_url():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def student_rows():
    rows = []
    with STUDENTS_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["name"].strip()
            if not name:
                continue
            rows.append(
                (
                    int(row["id"]),
                    row["identifier"].strip(),
                    row["identifier_kind"].strip(),
                    name,
                    row["school_year"].strip(),
                    row["intro_programming"].strip(),
                    int(row["skill_programming"]),
                    int(row["skill_data_stats"]),
                    int(row["skill_frontend_design"]),
                    int(row["skill_business_pitch"]),
                    _optional(row["working_style"]),
                    _optional(row["interests"]),
                    _optional(row["semester_goal"]),
                    row["submitted_at"].strip(),
                )
            )
    return rows


def _optional(value):
    text = value.strip()
    if text in ("", "#NAME?"):
        return None
    return text


def main():
    import psycopg

    rows = student_rows()
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM students")
            if cur.fetchone()[0]:
                print("students table already has rows; skipping seed")
                return
            cur.executemany(
                """
                INSERT INTO students (
                    id, identifier, identifier_kind, name, school_year,
                    intro_programming, skill_programming, skill_data_stats,
                    skill_frontend_design, skill_business_pitch, working_style,
                    interests, semester_goal, submitted_at
                ) OVERRIDING SYSTEM VALUE
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            cur.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('students', 'id'),
                    (SELECT MAX(id) FROM students)
                )
                """
            )
        print(f"seeded {len(rows)} students")


if __name__ == "__main__":
    main()
