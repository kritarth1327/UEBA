
from pathlib import Path

import pandas as pd

from app.services.cert_ingestion_service import CERTIngestionService


DATASET_DIR = Path("data/raw/r4.2")


def test_dataset_files_exist():
    required = [
        "logon.csv",
        "file.csv",
        "device.csv",
        "email.csv",
    ]

    missing = [
        name
        for name in required
        if not (DATASET_DIR / name).is_file()
    ]

    assert not missing, f"Missing CERT files: {missing}"


def test_logon_sample_can_be_read():
    sample = pd.read_csv(
        DATASET_DIR / "logon.csv",
        usecols=["date", "user", "activity"],
        nrows=100,
    )

    assert not sample.empty
    assert {"date", "user", "activity"}.issubset(sample.columns)


def test_ingestion_service_initializes():
    service = CERTIngestionService(
        dataset_dir=str(DATASET_DIR),
    )

    assert service.chunksize == 250_000
    assert service.dataset_dir == DATASET_DIR


def test_profile_initialization():
    profile = CERTIngestionService._empty_profile()

    assert profile["logon_count"] == 0
    assert profile["file_access_count"] == 0
    assert profile["email_count"] == 0
    assert "features" in profile


def test_date_parsing():
    dates = pd.Series(["01/02/2010 06:49:00"])

    parsed = CERTIngestionService._parse_dates(dates)

    assert parsed.notna().all()


def test_logon_aggregation_on_small_sample():
    service = CERTIngestionService(
        dataset_dir=str(DATASET_DIR),
        chunksize=100,
    )

    profiles = {}
    service._aggregate_logons(profiles, max_rows=500)

    assert profiles
    assert all(
        isinstance(user_id, str) and day is not None
        for user_id, day in profiles
    )
    assert all(
        profile["logon_count"] >= 0
        for profile in profiles.values()
    )

    total_logons = sum(
        profile["logon_count"]
        for profile in profiles.values()
    )
    assert total_logons > 0

def test_all_sources_aggregate_on_small_sample():
    service = CERTIngestionService(
        dataset_dir=str(DATASET_DIR),
        chunksize=100,
    )

    profiles = service.build_profiles(max_rows_per_file=500)

    assert profiles

    for (user_id, day), profile in profiles.items():
        assert user_id
        assert day is not None
        assert profile["logon_count"] >= 0
        assert profile["file_access_count"] >= 0
        assert profile["email_count"] >= 0
        assert profile["removable_device_events"] >= 0
        assert isinstance(profile["features"], dict)
