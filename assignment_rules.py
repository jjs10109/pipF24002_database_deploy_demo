"""Assign project groups from skill-cluster labels."""

import csv
from pathlib import Path

from cluster_model import predict_cluster

SKILL_COLUMNS = (
    "skill_programming",
    "skill_data_stats",
    "skill_frontend_design",
    "skill_business_pitch",
)
DATA_PATH = Path(__file__).resolve().parent / "class_dataset.csv"


def assign_groups(students, n_groups=8):
    """Label each student with a cluster and a group number from 1 to n_groups.

    Clusters are ordered from most students to fewest (smaller cluster number
    first when sizes match). Within a cluster, students are sorted by id.
    Groups are dealt in that order, and the count does not reset between clusters.
    """
    labeled = []
    for student in students:
        skills = [student[column] for column in SKILL_COLUMNS]
        labeled.append({
            "id": student["id"],
            "cluster": predict_cluster(skills),
        })

    by_cluster = {}
    for student in labeled:
        by_cluster.setdefault(student["cluster"], []).append(student)
    for members in by_cluster.values():
        members.sort(key=lambda student: student["id"])

    cluster_order = sorted(
        by_cluster,
        key=lambda cluster: (-len(by_cluster[cluster]), cluster),
    )
    ordered = []
    for cluster in cluster_order:
        ordered.extend(by_cluster[cluster])

    assignments = []
    for index, student in enumerate(ordered):
        assignments.append({
            "id": student["id"],
            "cluster": student["cluster"],
            "group": (index % n_groups) + 1,
        })
    return assignments


def _load_students(path):
    students = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            student = {"id": row["netid"]}
            for column in SKILL_COLUMNS:
                student[column] = int(row[column])
            students.append(student)
    return students


def _print_summary(assignments, n_groups):
    clusters = sorted({student["cluster"] for student in assignments})
    missing = 0
    for group in range(1, n_groups + 1):
        members = [student for student in assignments if student["group"] == group]
        counts = {cluster: 0 for cluster in clusters}
        for student in members:
            counts[student["cluster"]] += 1
        if any(count == 0 for count in counts.values()):
            missing += 1
        mix = ", ".join(f"cluster {cluster}: {counts[cluster]}" for cluster in clusters)
        print(f"Group {group}: {len(members)} students, {mix}")
    print(f"Groups missing a cluster: {missing}")


if __name__ == "__main__":
    roster = _load_students(DATA_PATH)
    groups = assign_groups(roster)
    _print_summary(groups, n_groups=8)
