
from pathlib import Path

import pandas as pd


class CERTIdentityService:
    """Resolve CERT identities using date-appropriate LDAP snapshots."""

    LDAP_COLUMNS = [
        "employee_name",
        "user_id",
        "email",
        "role",
        "business_unit",
        "functional_unit",
        "department",
        "team",
        "supervisor",
    ]

    def __init__(self, ldap_dir: str = "data/raw/r4.2/LDAP"):
        self.ldap_dir = Path(ldap_dir)
        self._snapshot_cache = {}

    def _snapshot_path(self, event_date):
        """Select the latest monthly snapshot not later than event_date."""
        month = pd.Timestamp(event_date).to_period("M")
        path = self.ldap_dir / f"{month}.csv"

        if path.is_file():
            return path

        available = sorted(self.ldap_dir.glob("????-??.csv"))
        eligible = []

        for candidate in available:
            try:
                candidate_month = pd.Period(candidate.stem, freq="M")
            except ValueError:
                continue

            if candidate_month <= month:
                eligible.append((candidate_month, candidate))

        if not eligible:
            return None

        return max(eligible, key=lambda item: item[0])[1]

    def _load_snapshot(self, snapshot_path):
        key = str(snapshot_path.resolve())

        if key in self._snapshot_cache:
            return self._snapshot_cache[key]

        df = pd.read_csv(
            snapshot_path,
            usecols=self.LDAP_COLUMNS,
            dtype="string",
        ).fillna("")

        users = {}
        email_to_user = {}
        internal_domains = set()

        for row in df.to_dict(orient="records"):
            user_id = row["user_id"].strip()
            email = row["email"].strip().lower()

            if not user_id:
                continue

            users[user_id] = row

            if email and "@" in email:
                email_to_user[email] = user_id
                internal_domains.add(email.rsplit("@", 1)[1])

        snapshot = {
            "users": users,
            "email_to_user": email_to_user,
            "internal_domains": internal_domains,
        }

        self._snapshot_cache[key] = snapshot
        return snapshot

    def get_user(self, user_id: str, event_date):
        path = self._snapshot_path(event_date)

        if path is None:
            return None

        snapshot = self._load_snapshot(path)
        return snapshot["users"].get(user_id)

    def classify_recipient(self, recipient: str, event_date):
        if not recipient or not recipient.strip():
            return "unknown"

        address = recipient.strip().lower()

        if "@" not in address:
            return "unknown"

        domain = address.rsplit("@", 1)[1].strip()

        if not domain or "." not in domain:
            return "unknown"

        path = self._snapshot_path(event_date)

        if path is None:
            return "unknown"

        snapshot = self._load_snapshot(path)

        if domain in snapshot["internal_domains"]:
            return "internal"

        return "external"

    def classify_recipients(self, recipients: str, event_date):
        counts = {
            "internal": 0,
            "external": 0,
            "unknown": 0,
        }

        if not recipients or not recipients.strip():
            return counts

        for recipient in recipients.split(";"):
            recipient = recipient.strip()

            if not recipient:
                continue

            classification = self.classify_recipient(
                recipient,
                event_date,
            )
            counts[classification] += 1

        return counts
