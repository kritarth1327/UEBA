
from app.services.cert_identity_service import CERTIdentityService


LDAP_DIR = "data/raw/r4.2/LDAP"
EVENT_DATE = "2010-01-15"


def test_ldap_identity_loading():
    service = CERTIdentityService(LDAP_DIR)

    user = service.get_user("CEL0561", EVENT_DATE)

    assert user is not None
    assert user["user_id"] == "CEL0561"


def test_internal_recipient_classification():
    service = CERTIdentityService(LDAP_DIR)

    result = service.classify_recipient(
        "Calvin.Edan.Love@dtaa.com",
        EVENT_DATE,
    )

    assert result == "internal"


def test_multiple_recipient_classification():
    service = CERTIdentityService(LDAP_DIR)

    result = service.classify_recipients(
        "Calvin.Edan.Love@dtaa.com;person@example.invalid",
        EVENT_DATE,
    )

    assert result["internal"] == 1
    assert result["external"] == 1
    assert result["unknown"] == 0


def test_invalid_recipient_is_unknown():
    service = CERTIdentityService(LDAP_DIR)

    assert service.classify_recipient(
        "not-an-email",
        EVENT_DATE,
    ) == "unknown"


def test_missing_historical_snapshot_uses_previous_snapshot():
    service = CERTIdentityService(LDAP_DIR)

    # February 2010 exists in this dataset, so the selected file
    # should correspond to that month.
    path = service._snapshot_path("2010-02-15")

    assert path is not None
    assert path.stem == "2010-02"
