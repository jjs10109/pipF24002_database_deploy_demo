# Integrating the group models

Instructions for an agent working in the app repo. Do not edit `cluster_model.py` or `assignment_rules.py`. Change the app so it fits these files. Backend only: do not change the frontend. Do not add scikit-learn or pandas.

## 1. What these two files do

`cluster_model.py` is the fitted model: it stores three k-means centroids as plain numbers, and `predict_cluster` returns the nearest centroid for one student's four skill ratings. `assignment_rules.py` calls that function for every student, then deals the class into groups round-robin, largest cluster first and sorted by id inside a cluster, without restarting the count for each cluster. The app calls these two functions when a request arrives and does not refit anything.

## 2. Files to copy

Copy these two files into a new `model/` folder at the app repo root, next to `app.py`:

- `cluster_model.py`
- `assignment_rules.py`

Leave both files byte-for-byte as they are. `assignment_rules.py` contains `from cluster_model import predict_cluster`. That import looks for `cluster_model` on `sys.path`, not inside the `model` package. Before importing, add the `model` directory to `sys.path` (the directory that contains the two files). Do not rewrite the import and do not move either file to the repo root.

Also copy this `INTEGRATION.md` into `model/` so it sits with the code. The app does not need to read it at runtime.

## 3. The two functions

Ratings are never scaled. Their order is `skill_programming`, `skill_data_stats`, `skill_frontend_design`, `skill_business_pitch`.

`predict_cluster(skills)` takes one sequence of those four ratings and returns an integer cluster label.

```python
predict_cluster([3, 4, 2, 5])  # 0
```

`assign_groups(students, n_groups=8)` takes the whole class and returns one dict per student with `id`, `cluster`, and `group`. `group` is a number from 1 to `n_groups`. Each student dict must have `id` plus the four skill keys named above. The function needs every student at once, because the deal depends on which cluster is largest.

```python
assign_groups([{
    "id": "jq2306",
    "skill_programming": 3,
    "skill_data_stats": 4,
    "skill_frontend_design": 2,
    "skill_business_pitch": 5,
}])
# [{"id": "jq2306", "cluster": 0, "group": 1}]
```

`assign_groups` returns each person's cluster so the app can count. The HTTP response must not pass that per-person cluster through. See section 5.

## 4. Where the data comes from

The models were fit from `class_dataset.csv`. The running app reads the Postgres `students` table. `schema.sql` creates that table. `seed.py` loads it from `database/students.csv` when the table is still empty, using `DATABASE_URL`.

Build one dict per student and pass the list to `assign_groups`. For each model input:

| What the model expects | CSV column | Postgres table.column | Difference |
|---|---|---|---|
| `id` | `netid` | `students.identifier` | Use the identifier string as `id`. `students.id` is a generated integer primary key and must not be passed to `assign_groups`. Sorting uses `id`, so the integer would change the groups. The CSV named this column `netid`, but the values mix netids (`jq2306`), emails (`yo2162@nyu.edu`), and N-numbers (`N16059079`). `students.identifier_kind` records which kind (`netid`, `email`, `n_number`). The model does not read `identifier_kind`. |
| `skill_programming` | `skill_programming` | `students.skill_programming` | Same name. Postgres stores `smallint`, checked between 1 and 5. Pass the number through. Do not scale it. |
| `skill_data_stats` | `skill_data_stats` | `students.skill_data_stats` | Same as above. |
| `skill_frontend_design` | `skill_frontend_design` | `students.skill_frontend_design` | Same as above. |
| `skill_business_pitch` | `skill_business_pitch` | `students.skill_business_pitch` | Same as above. |

The endpoint also needs `students.name` for the member lists. That column is not a model input. Do not attach a cluster to a name in the JSON.

These CSV columns are not inputs: `tools`, `availability`, `working_style`, `interests`, `semester_goal`, `submitted_at`, `school_year`, `intro_programming`. Leave them out of the dict. `school_year` text differs from the database (`Senior` in the CSV, enum `senior` in Postgres; `First-year` becomes `first_year`), and the models do not read it.

Query to load the rows:

```sql
SELECT identifier, name, skill_programming, skill_data_stats,
       skill_frontend_design, skill_business_pitch
FROM students
```

When `DATABASE_URL` is unset, the app serves a local SQLite file instead of Postgres. Read the same six fields from that local `students` table, and keep using `identifier` as `id`. `database/students.csv` already has `identifier` and the four skill columns.

## 5. Backend

Add `GET /api/groups`. Do not change any existing page.

The handler reads every student with the query above, calls `assign_groups` with the default `n_groups=8`, and returns JSON. Shape:

```json
{
  "n_groups": 8,
  "groups": [
    {
      "group": 1,
      "members": ["Edward Huang", "Jin Michael Qian"],
      "cluster_counts": {"0": 2, "1": 0, "2": 0}
    }
  ],
  "clusters": [
    {
      "cluster": 0,
      "students": 13,
      "centroid": [2.923076923076923, 3.076923076923077, 2.8461538461538463, 4.0]
    }
  ],
  "groups_missing_a_cluster": 6
}
```

- `groups` has one object for every group number from 1 through `n_groups`, including a group with no students.
- `members` is a list of name strings only. Do not put `id`, skills, or `cluster` on a member.
- `cluster_counts` is an object whose keys are the cluster numbers as strings. Include every cluster that appears in the class, and include a count of 0 when a group has nobody from that cluster.
- `clusters` has one object per cluster that appears. `students` is the number of students in that cluster, not a list of people. `centroid` is the four numbers from `cluster_model.CENTROIDS` for that label, in skill-column order. Do not list who is in the cluster.
- `groups_missing_a_cluster` is how many groups have a 0 in `cluster_counts`.

An empty `students` table returns `n_groups` 8, eight groups with empty `members`, `clusters` as an empty list, and `groups_missing_a_cluster` 0.

## 6. Frontend

Do not change templates or add a page.

A later page can render `groups` in group-number order. Each `members` list is the names in that group. `cluster_counts` says how many people in that group came from each skill cluster, without saying which person is which. `clusters` describes the kinds of student: `students` is the size of that kind, and `centroid` is the four average ratings in the order programming, data/stats, frontend design, business pitch. `groups_missing_a_cluster` is the number of groups that are missing at least one of those kinds. `n_groups` is how many groups were dealt.

## 7. Packaging

No packaging file has to change for these two modules to be in the deployed image.

- `Dockerfile` runs `COPY . .` after installing `requirements.txt`. A `model/` folder that is in the repo is copied into the image.
- `.dockerignore` ignores `*.md`, so this instructions file is left out of the image. It does not ignore `*.py`.
- `requirements.txt` stays `flask`, `psycopg[binary]`, and `gunicorn`. The model files use only the Python standard library.
- `railway.toml` already applies `schema.sql`, runs `python seed.py`, and starts `python app.py`. The new route is part of `app.py`. Nothing in that file changes because of the model files.

The image working directory is `/app`. Adding `model/` to `sys.path` in `app.py` is what makes `import cluster_model` succeed there. That is application code, not a Docker or Railway setting.

## 8. Test

Start the app the same way it was started in the deploy lab. In another terminal, against the port in `PORT` (the default in `app.py` is 5000):

```bash
curl http://127.0.0.1:5000/api/groups
```

The response is JSON, with no error. Expect:

- `n_groups` is 8.
- Group sizes (`members` lengths), in order from group 1 to group 8, are 3, 3, 3, 3, 3, 3, 3, 2.
- `cluster_counts` for those groups are `{"0": 2, "1": 1, "2": 0}`, `{"0": 2, "1": 1, "2": 0}`, `{"0": 2, "1": 0, "2": 1}`, `{"0": 2, "1": 0, "2": 1}`, `{"0": 2, "1": 0, "2": 1}`, `{"0": 1, "1": 1, "2": 1}`, `{"0": 1, "1": 1, "2": 1}`, `{"0": 1, "1": 1, "2": 0}`.
- `clusters` reports 13 students in cluster 0, 5 in cluster 1, and 5 in cluster 2. Centroids are the three tuples in `cluster_model.CENTROIDS`, in label order.
- `groups_missing_a_cluster` is 6.

No member object includes a cluster. The existing HTML page is unchanged.
