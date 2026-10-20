import math
from app.pipeline.schema import (FEATURE_NAMES, FEATURES, SCHEMA_VERSION, SPEDIA, CERT_R42, available_features,
                                 schema_description, vectorize, TYPED_COLUMN_FEATURES, LABEL_COLUMNS)


def test_feature_names_unique_and_ordered():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert FEATURE_NAMES[0] == "logon_count"


def test_labels_are_never_features():
    assert not set(LABEL_COLUMNS) & set(FEATURE_NAMES)


def test_vectorize_marks_missing_as_nan_not_zero():
    v = vectorize({"logon_count": 3, "email_count": None})
    assert v[FEATURE_NAMES.index("logon_count")] == 3.0
    assert math.isnan(v[FEATURE_NAMES.index("email_count")])
    assert math.isnan(v[FEATURE_NAMES.index("http_request_count")])  # absent key
    assert len(v) == len(FEATURE_NAMES)


def test_vectorize_custom_order():
    assert vectorize({"a_unknown": 1, "email_count": 2}, ["email_count"]) == [2.0]


def test_dataset_availability_is_explicit():
    sp, ce = available_features(SPEDIA), available_features(CERT_R42)
    assert "command_exec_count" in sp and "command_exec_count" not in ce
    assert "total_session_duration" not in sp + ce
    assert "file_copied_removable" not in sp + ce
    assert "file_copied_removable" in available_features(CERT_R42, ["file_copied_removable"])


def test_typed_columns_exist_on_model():
    from app.models.behavior import DailyBehaviorProfile
    for n in TYPED_COLUMN_FEATURES:
        assert hasattr(DailyBehaviorProfile, n)


def test_schema_description_contract():
    d = schema_description()
    assert d["schema_version"] == SCHEMA_VERSION
    assert [f["name"] for f in d["features"]] == list(FEATURE_NAMES)
    assert [f["index"] for f in d["features"]] == list(range(len(FEATURES)))
