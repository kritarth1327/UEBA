from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from app.pipeline.adapters.base import IngestStats
from app.pipeline.adapters.cert import CertR42Adapter
from app.pipeline.features import BusinessHours, DailyAggregator


DEFAULT_DATA_DIR = Path.home() / "Downloads" / "CERT_r4.2" / "r4.2"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CHUNK_SIZE = 50_000


def main() -> int:
    data_dir = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_DATA_DIR

    if not data_dir.is_dir():
        print(f"ERROR: CERT dataset directory not found: {data_dir}")
        print("Usage: python scripts/build_cert_features.py /path/to/r4.2")
        return 1

    adapter = CertR42Adapter()
    stats = IngestStats()
    aggregator = DailyAggregator(
        available=adapter.available,
        bh=BusinessHours(),
        has_labels=adapter.has_labels,
    )

    print("=" * 64)
    print("CERT r4.2 | USER-DAY FEATURE BUILD")
    print("=" * 64)
    print(f"Dataset directory : {data_dir}")
    print(f"Chunk size        : {CHUNK_SIZE:,}")
    print(f"Available features: {len(adapter.available)}")
    print(f"Ground-truth labels available in event logs: {adapter.has_labels}")
    print("Raw content fields: excluded")
    print("-" * 64)

    started = time.time()
    chunks = 0

    try:
        for events in adapter.iter_events(
            directory=data_dir,
            chunksize=CHUNK_SIZE,
            stats=stats,
        ):
            aggregator.add_chunk(events)
            chunks += 1

            if chunks == 1 or chunks % 25 == 0:
                elapsed = max(time.time() - started, 0.001)
                rate = stats.rows_read / elapsed
                print(
                    f"Chunks processed: {chunks:,} | "
                    f"Rows read: {stats.rows_read:,} | "
                    f"Accepted: {stats.rows_accepted:,} | "
                    f"Rejected: {stats.rows_rejected:,} | "
                    f"Rate: {rate:,.0f} rows/s"
                )

        result = aggregator.finalize()

        if result.empty:
            print("ERROR: No user-day records were produced.")
            print(json.dumps(stats.as_dict(), indent=2))
            return 1

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        csv_path = OUTPUT_DIR / "cert_user_day_features.csv"
        metadata_path = OUTPUT_DIR / "cert_user_day_features.meta.json"

        result.to_csv(csv_path, index=False)

        feature_columns = [
            c for c in adapter.available if c in result.columns
        ]
        null_rates = {
            col: round(float(result[col].isna().mean()), 4)
            for col in feature_columns
        }

        metadata = {
            "dataset": adapter.name,
            "schema_version": "1.0.0",
            "granularity": "user-day",
            "has_event_ground_truth_labels": adapter.has_labels,
            "removable_media_proxy_enabled": adapter.file_is_removable_copy,
            "chunk_size": CHUNK_SIZE,
            "chunks_processed": chunks,
            "user_day_rows": int(len(result)),
            "unique_users": int(result["user_id"].nunique()),
            "date_min": str(result["date"].min()),
            "date_max": str(result["date"].max()),
            "feature_columns": feature_columns,
            "feature_null_rates": null_rates,
            "ingestion_stats": stats.as_dict(),
            "elapsed_seconds": round(time.time() - started, 2),
            "label_warning": (
                "CERT event logs do not provide per-event ground truth. "
                "Do not treat missing anomaly labels as normal labels."
            ),
            "feature_warning": (
                "file_copied_removable is a proxy derived from CERT file-event "
                "semantics; it is not evidence of malicious intent."
            ),
        }

        metadata_path.write_text(json.dumps(metadata, indent=2))

        print("-" * 64)
        print("BUILD COMPLETE")
        print(f"Chunks processed : {chunks:,}")
        print(f"Rows read        : {stats.rows_read:,}")
        print(f"Rows accepted    : {stats.rows_accepted:,}")
        print(f"Rows rejected    : {stats.rows_rejected:,}")
        print(f"User-day records : {len(result):,}")
        print(f"Unique users     : {result['user_id'].nunique():,}")
        print(f"Date range       : {result['date'].min()} to {result['date'].max()}")
        print(f"Feature columns  : {len(feature_columns)}")
        print(f"CSV output       : {csv_path}")
        print(f"Metadata output  : {metadata_path}")
        print(f"Elapsed seconds  : {metadata['elapsed_seconds']}")
        print("=" * 64)

        print("\nFeature missingness:")
        for col, rate in null_rates.items():
            print(f"  {col:<32} {rate:>7.1%}")

        if "anomalous_event_count" in result.columns:
            if result["anomalous_event_count"].notna().any():
                print(
                    "\nWARNING: Unexpected event labels detected. "
                    "Inspect the source before any supervised training."
                )
            else:
                print("\nPASS: No fabricated CERT anomaly labels.")

        return 0

    except KeyboardInterrupt:
        print("\nBuild interrupted. Do not use partial output as a completed dataset.")
        return 130
    except Exception as exc:
        print(f"\nERROR during CERT feature build: {type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
