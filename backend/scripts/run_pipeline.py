"""Reproducible pipeline CLI (no HTTP server required).

    python scripts/run_pipeline.py ingest --dataset spedia --path /abs/path/logs_SPEDIA_annotated_en.csv
    python scripts/run_pipeline.py baselines
    python scripts/run_pipeline.py score
    python scripts/run_pipeline.py all --dataset spedia --path ...

Run `python -m alembic upgrade head` first. The CLI may read files outside data/raw (API calls may not).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.baseline_service import BaselineService  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402
from app.services.scoring_service import ScoringService  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["ingest", "baselines", "score", "all"])
    ap.add_argument("--dataset", choices=["spedia", "cert_r42"], default="spedia")
    ap.add_argument("--path"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--as-of", type=date.fromisoformat)
    a = ap.parse_args()
    with SessionLocal() as db:
        if a.command in ("ingest", "all"):
            print(json.dumps(IngestionService(db).ingest(
                a.dataset, a.path, a.force, allow_outside_raw_dir=True), indent=2, default=str))
        if a.command in ("baselines", "all"):
            res = BaselineService(db).generate_all(a.as_of)
            print(json.dumps({"persisted": sum(r["persisted"] for r in res), "results": res}, indent=2, default=str))
        if a.command in ("score", "all"):
            print(json.dumps(ScoringService(db).score_range(), indent=2, default=str))


if __name__ == "__main__":
    main()
