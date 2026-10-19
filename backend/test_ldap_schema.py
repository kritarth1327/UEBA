
from pathlib import Path

import pandas as pd


LDAP_DIR = Path("data/raw/r4.2/LDAP")


def test_ldap_schema():
    path = LDAP_DIR / "2010-01.csv"

    df = pd.read_csv(path, nrows=10)

    print("\nLDAP columns:")
    print(df.columns.tolist())

    print("\nLDAP sample:")
    print(df.head(5).to_string(index=False))

    assert not df.empty
    assert "user_id" not in df.columns or len(df.columns) > 0
