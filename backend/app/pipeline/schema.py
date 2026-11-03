
"""Shared behavioural feature contract (schema v1).

This module is the single source of truth for feature names, order, dtype and units.
The baseline engine, ML service, ANN service, risk engine, API and frontend must all
derive from it. Changing names/order requires bumping SCHEMA_VERSION.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

SCHEMA_VERSION = "1.0.0"

SPEDIA = "spedia"
CERT_R42 = "cert_r42"


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: str
    unit: str
    description: str
    # Datasets whose adapter can populate this feature.
    # Unsupported features remain unavailable, not zero.
    sources: Tuple[str, ...]
    db_column: Optional[str] = None


FEATURES: Tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "logon_count", "int", "events",
        "Successful logon / session-open events",
        (SPEDIA, CERT_R42), "logon_count",
    ),
    FeatureSpec(
        "after_hours_logons", "int", "events",
        "Logons outside business hours or on weekends",
        (SPEDIA, CERT_R42), "after_hours_logons",
    ),
    FeatureSpec(
        "failed_logon_count", "int", "events",
        "Failed authentication events",
        (SPEDIA,),
    ),
    FeatureSpec(
        "file_access_count", "int", "events",
        "File access events (user-attributed)",
        (SPEDIA,), "file_access_count",
    ),
    FeatureSpec(
        "file_copied_removable", "int", "events",
        "File copies to removable media (only when the source documents this)",
        (), "file_copied_removable",
    ),
    FeatureSpec(
        "file_integrity_event_count", "int", "events",
        "Host file-integrity events (added/changed/deleted)",
        (SPEDIA,),
    ),
    FeatureSpec(
        "email_count", "int", "emails",
        "Emails sent",
        (SPEDIA, CERT_R42), "email_count",
    ),
    FeatureSpec(
        "email_external_count", "int", "emails",
        "Emails with at least one recipient outside internal domains",
        (SPEDIA, CERT_R42), "email_external_count",
    ),
    FeatureSpec(
        "email_attachment_count", "int", "attachments",
        "Total attachments across sent emails",
        (SPEDIA, CERT_R42), "email_attachment_count",
    ),
    FeatureSpec(
        "email_total_bytes", "float", "bytes",
        "Total size of sent emails",
        (SPEDIA, CERT_R42),
    ),
    FeatureSpec(
        "http_request_count", "int", "requests",
        "Web requests",
        (SPEDIA, CERT_R42), "http_request_count",
    ),
    FeatureSpec(
        "http_after_hours_count", "int", "requests",
        "Web requests outside business hours or on weekends",
        (SPEDIA, CERT_R42), "http_after_hours_count",
    ),
    FeatureSpec(
        "removable_device_events", "int", "events",
        "Removable device connect + disconnect events",
        (SPEDIA, CERT_R42), "removable_device_events",
    ),
    FeatureSpec(
        "total_session_duration", "float", "seconds",
        "Summed session length; unavailable until reliable open/close "
        "pairing is validated for a dataset",
        (), "total_session_duration",
    ),
    FeatureSpec(
        "command_exec_count", "int", "events",
        "Shell/command executions (audit logs)",
        (SPEDIA,),
    ),
    FeatureSpec(
        "after_hours_event_count", "int", "events",
        "All attributed events outside business hours or on weekends",
        (SPEDIA, CERT_R42),
    ),
)

FEATURE_NAMES: Tuple[str, ...] = tuple(f.name for f in FEATURES)
FEATURE_BY_NAME: Dict[str, FeatureSpec] = {
    f.name: f for f in FEATURES
}
TYPED_COLUMN_FEATURES: Tuple[str, ...] = tuple(
    f.name for f in FEATURES if f.db_column
)

# Label / bookkeeping columns. NEVER model inputs.
LABEL_COLUMNS: Tuple[str, ...] = (
    "event_count",
    "anomalous_event_count",
)


def available_features(
    dataset: str,
    overrides: Optional[Iterable[str]] = None,
) -> List[str]:
    """Return features supported by a dataset and explicit overrides."""
    base = {f.name for f in FEATURES if dataset in f.sources}

    if overrides:
        base |= set(overrides)

    return [name for name in FEATURE_NAMES if name in base]


def is_missing(value) -> bool:
    """Return whether a scalar feature value is missing."""
    return value is None or (
        isinstance(value, float) and math.isnan(value)
    )


def vectorize(
    features: Mapping[str, Optional[float]],
    names: Iterable[str] = FEATURE_NAMES,
) -> List[float]:
    """Create a schema-ordered vector; missing values become NaN."""
    out = []

    for name in names:
        value = features.get(name)
        out.append(
            float("nan") if is_missing(value) else float(value)
        )

    return out


def schema_description() -> Dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "features": [
            {
                "index": i,
                "name": feature.name,
                "dtype": feature.dtype,
                "unit": feature.unit,
                "description": feature.description,
                "sources": list(feature.sources),
            }
            for i, feature in enumerate(FEATURES)
        ],
        "label_columns_excluded_from_models": list(LABEL_COLUMNS),
        "missing_value_policy": (
            "unavailable => null in API / NaN in vectors; typed DB "
            "columns store 0 and the feature is listed in unavailable_features"
        ),
    }
