
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASETS = {
    "SPEDIA": PROJECT_ROOT / "data" / "raw" / "logs_SPEDIA_annotated_en.csv",
    "CERT logon": Path.home() / "Downloads" / "CERT_r4.2" / "r4.2" / "logon.csv",
    "CERT device": Path.home() / "Downloads" / "CERT_r4.2" / "r4.2" / "device.csv",
    "CERT file": Path.home() / "Downloads" / "CERT_r4.2" / "r4.2" / "file.csv",
    "CERT email": Path.home() / "Downloads" / "CERT_r4.2" / "r4.2" / "email.csv",
    "CERT http": Path.home() / "Downloads" / "CERT_r4.2" / "r4.2" / "http.csv",
}


def inspect_dataset(name, path):
    print(f"\n{'=' * 70}")
    print(f"DATASET: {name}")
    print(f"PATH: {path}")
    print("=" * 70)

    if not path.exists():
        print("STATUS: FILE NOT FOUND")
        return

    try:
        df = pd.read_csv(path, nrows=5, low_memory=False)

        print(f"STATUS: FOUND")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Sample rows: {len(df)}")
        print("\nSample:")
        print(df.head(3).to_string(index=False))

        if name == "SPEDIA":
            label = "Anomaly"
            if label in df.columns:
                print("\nAnomaly sample values:")
                print(df[label].value_counts(dropna=False).to_string())

    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")


def main():
    for name, path in DATASETS.items():
        inspect_dataset(name, path)


if __name__ == "__main__":
    main()
