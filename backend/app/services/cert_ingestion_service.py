
from collections import defaultdict
from pathlib import Path

import pandas as pd

from app.services.cert_identity_service import CERTIdentityService


class CERTIngestionService:
    """Aggregate CERT r4.2 activity logs into user-day profiles."""

    def __init__(
        self,
        dataset_dir: str = "data/raw/r4.2",
        chunksize: int = 250_000,
        identity_service=None,
    ):
        self.dataset_dir = Path(dataset_dir)
        self.chunksize = chunksize
        self.identity_service = identity_service or CERTIdentityService(
            str(self.dataset_dir / "LDAP")
        )

    @staticmethod
    def _empty_profile():
        return {
            "logon_count": 0,
            "after_hours_logons": 0,
            "file_access_count": 0,
            "file_copied_removable": 0,
            "email_count": 0,
            "email_external_count": 0,
            "email_attachment_count": 0,
            "http_request_count": 0,
            "http_after_hours_count": 0,
            "removable_device_events": 0,
            "total_session_duration": 0.0,
            "features": defaultdict(float),
        }

    @staticmethod
    def _parse_dates(series):
        return pd.to_datetime(series, errors="coerce", format="mixed")

    @staticmethod
    def _is_after_hours(dates):
        return (dates.dt.hour < 8) | (dates.dt.hour >= 18)

    def _read_chunks(
        self,
        filename,
        columns,
        dtypes,
        max_rows=None,
    ):
        path = self.dataset_dir / filename

        if not path.is_file():
            raise FileNotFoundError(f"CERT file not found: {path}")

        rows_read = 0

        for chunk in pd.read_csv(
            path,
            usecols=columns,
            chunksize=self.chunksize,
            dtype=dtypes,
        ):
            if max_rows is not None:
                remaining = max_rows - rows_read
                if remaining <= 0:
                    break
                chunk = chunk.iloc[:remaining]

            rows_read += len(chunk)

            dates = self._parse_dates(chunk["date"])

            chunk = chunk.assign(
                parsed_date=dates.dt.date,
                after_hours=self._is_after_hours(dates),
            ).dropna(subset=["parsed_date", "user"])

            chunk["user"] = chunk["user"].str.strip()
            chunk = chunk[
                chunk["user"].notna() & chunk["user"].ne("")
            ]

            yield chunk

            if max_rows is not None and rows_read >= max_rows:
                break

    def _aggregate_logons(self, profiles, max_rows=None):
        for chunk in self._read_chunks(
            "logon.csv",
            ["date", "user", "activity"],
            {"user": "string", "activity": "string"},
            max_rows=max_rows,
        ):
            for row in chunk.itertuples(index=False):
                key = (row.user, row.parsed_date)
                profile = profiles.setdefault(
                    key, self._empty_profile()
                )

                activity = str(row.activity).strip().lower()

                if activity == "logon":
                    profile["logon_count"] += 1
                    if row.after_hours:
                        profile["after_hours_logons"] += 1

                profile["features"][
                    f"logon_activity_{activity}"
                ] += 1

    def _aggregate_files(self, profiles, max_rows=None):
        for chunk in self._read_chunks(
            "file.csv",
            ["date", "user", "filename"],
            {"user": "string", "filename": "string"},
            max_rows=max_rows,
        ):
            for row in chunk.itertuples(index=False):
                key = (row.user, row.parsed_date)
                profile = profiles.setdefault(
                    key, self._empty_profile()
                )
                profile["file_access_count"] += 1

    def _aggregate_devices(self, profiles, max_rows=None):
        for chunk in self._read_chunks(
            "device.csv",
            ["date", "user", "activity"],
            {"user": "string", "activity": "string"},
            max_rows=max_rows,
        ):
            for row in chunk.itertuples(index=False):
                key = (row.user, row.parsed_date)
                profile = profiles.setdefault(
                    key, self._empty_profile()
                )

                activity = str(row.activity).strip().lower()
                profile["features"][
                    f"device_activity_{activity}"
                ] += 1

                if activity in {"connect", "disconnect"}:
                    profile["removable_device_events"] += 1

    def _aggregate_emails(self, profiles, max_rows=None):
        for chunk in self._read_chunks(
            "email.csv",
            ["date", "user", "to", "size", "attachments"],
            {
                "user": "string",
                "to": "string",
                "size": "float64",
                "attachments": "string",
            },
            max_rows=max_rows,
        ):
            for row in chunk.itertuples(index=False):
                key = (row.user, row.parsed_date)
                profile = profiles.setdefault(
                    key, self._empty_profile()
                )

                profile["email_count"] += 1

                counts = self.identity_service.classify_recipients(
                    str(row.to) if pd.notna(row.to) else "",
                    row.parsed_date,
                )

                profile["email_external_count"] += counts["external"]
                profile["features"][
                    "email_internal_recipient_count"
                ] += counts["internal"]
                profile["features"][
                    "email_unknown_recipient_count"
                ] += counts["unknown"]

                if pd.notna(row.size):
                    profile["features"][
                        "email_size_total"
                    ] += float(row.size)

                if pd.notna(row.attachments):
                    try:
                        count = int(float(row.attachments))
                        profile["email_attachment_count"] += max(
                            count, 0
                        )
                    except (ValueError, TypeError):
                        pass

    def build_profiles(self, max_rows_per_file=None):
        """Return {(user_id, date): profile_dict}."""
        if not self.dataset_dir.is_dir():
            raise FileNotFoundError(
                "CERT dataset directory not found: "
                f"{self.dataset_dir.resolve()}"
            )

        required_files = [
            "logon.csv",
            "file.csv",
            "device.csv",
            "email.csv",
        ]

        missing = [
            name for name in required_files
            if not (self.dataset_dir / name).is_file()
        ]

        if missing:
            raise FileNotFoundError(
                f"Missing required CERT files: {', '.join(missing)}"
            )

        profiles = {}

        self._aggregate_logons(profiles, max_rows_per_file)
        self._aggregate_files(profiles, max_rows_per_file)
        self._aggregate_devices(profiles, max_rows_per_file)
        self._aggregate_emails(profiles, max_rows_per_file)

        result = {}

        for key, profile in profiles.items():
            profile["features"] = dict(profile["features"])
            result[key] = profile

        return result
