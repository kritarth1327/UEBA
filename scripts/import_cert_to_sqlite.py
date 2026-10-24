import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "processed" / "daily_behavior_profiles.csv"
DB_PATH = ROOT / "backend" / "ueba.db"

FEATURES = [
    "logon_count",
    "after_hours_logons",
    "file_copied_removable",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
    "total_session_duration",
]

INTEGER_FEATURES = [
    "logon_count",
    "after_hours_logons",
    "file_access_count",
    "file_copied_removable",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
]

if not CSV_PATH.exists():
    raise SystemExit(f"CSV not found: {CSV_PATH}")

if not DB_PATH.exists():
    raise SystemExit(f"Database not found: {DB_PATH}")

timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(
    sep=" ", timespec="seconds"
)

conn = sqlite3.connect(DB_PATH)

try:
    # Refuse to import into non-empty tables.
    user_count = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    profile_count = conn.execute(
        "SELECT COUNT(*) FROM daily_behavior_profiles"
    ).fetchone()[0]

    if user_count != 0 or profile_count != 0:
        raise SystemExit(
            "Import cancelled: users or daily_behavior_profiles "
            f"already contain records (users={user_count}, "
            f"profiles={profile_count}). No records were imported."
        )

    # Read and validate the complete CSV before inserting records.
    with CSV_PATH.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required = {
            "user_id", "date", *INTEGER_FEATURES,
            "total_session_duration",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise SystemExit(f"CSV is missing columns: {sorted(missing)}")

        users = set()
        seen_profiles = set()
        profile_count_csv = 0

        def rows():
            global profile_count_csv

            for row in reader:
                user_id = row["user_id"].strip()
                profile_date = row["date"].strip()

                if not user_id:
                    raise ValueError("CSV contains an empty user_id.")

                # Validate dates and numeric values.
                datetime.strptime(profile_date, "%Y-%m-%d")

                for name in INTEGER_FEATURES:
                    value = int(row[name])
                    if value < 0:
                        raise ValueError(
                            f"Negative value in {name}: {value}"
                        )

                duration = float(row["total_session_duration"])
                if duration < 0:
                    raise ValueError(
                        f"Negative session duration: {duration}"
                    )

                key = (user_id, profile_date)
                if key in seen_profiles:
                    raise ValueError(
                        f"Duplicate user/date profile: {key}"
                    )

                users.add(user_id)
                seen_profiles.add(key)
                profile_count_csv += 1

                yield row

        # Prepare records for a single atomic transaction.
        profile_rows = []
        for row in rows():
            profile_rows.append((
                row["user_id"].strip(),
                row["date"].strip(),
                *(int(row[name]) for name in INTEGER_FEATURES),
                float(row["total_session_duration"]),
                json.dumps({
                    name: float(row[name]) for name in FEATURES
                }),
                timestamp,
            ))

    print(f"Validated profiles: {profile_count_csv}")
    print(f"Unique users: {len(users)}")
    print("Importing records...")

    # Use a transaction so a failed import can be rolled back.
    with conn:
        conn.executemany(
            """
            INSERT INTO users (
                user_id, employee_name, email, department,
                role, supervisor, is_active, created_at, updated_at
            )
            VALUES (?, ?, NULL, NULL, NULL, NULL, 1, ?, ?)
            """,
            [
                (user_id, user_id, timestamp, timestamp)
                for user_id in sorted(users)
            ],
        )

        conn.executemany(
            """
            INSERT INTO daily_behavior_profiles (
                user_id, date, logon_count, after_hours_logons,
                file_access_count, file_copied_removable,
                email_count, email_external_count,
                email_attachment_count, http_request_count,
                http_after_hours_count, removable_device_events,
                total_session_duration, features_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            profile_rows,
        )

    print("\nImport completed successfully!")
    print(
        "Users in database:",
        conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
    )
    print(
        "Daily profiles in database:",
        conn.execute(
            "SELECT COUNT(*) FROM daily_behavior_profiles"
        ).fetchone()[0],
    )
    print(
        "First user:",
        conn.execute(
            "SELECT user_id FROM users ORDER BY user_id LIMIT 1"
        ).fetchone()[0],
    )

finally:
    conn.close()
