from datetime import datetime
import numpy as np
import pandas as pd
import pytest

from app.pipeline.adapters.base import IngestStats, normalize_user, has_external_recipient, file_fingerprint
from app.pipeline.adapters.spedia import SpediaAdapter, USECOLS
from app.pipeline.adapters.cert import CertR42Adapter
from app.pipeline.features import DailyAggregator, BusinessHours
from tests.helpers import spedia_row, write_csv, SECRET


def run(adapter, src, bh=BusinessHours(8, 18, False), chunk=1000):
    st = IngestStats(); agg = DailyAggregator(adapter.available, bh, adapter.has_labels)
    for ev in adapter.iter_events(src, chunk, st):
        agg.add_chunk(ev)
    return agg.finalize(), st


def test_normalize_user():
    s = pd.Series(["root(uid=0)", " Ubuntu(uid=1000) ", "IRENE", "", None, "DTAA/ACM2278"])
    out = normalize_user(s).tolist()
    assert out[:3] == ["root", "ubuntu", "irene"] and pd.isna(out[3]) and pd.isna(out[4])
    assert normalize_user(s, domain_prefix=True).iloc[5] == "acm2278"


def test_typo_users_are_not_fuzzy_merged():
    assert normalize_user(pd.Series(["humbeMar", "humberto"])).nunique() == 2


def test_external_recipient_detection():
    s = pd.Series(["a@dtaa.com;b@DTAA.com", "a@dtaa.com;x@gmail.com", "", "c@dtaa.com,d@yahoo.com"])
    assert has_external_recipient(s, ["dtaa.com"]).tolist() == [False, True, False, True]


def test_adapter_never_reads_leaky_or_content_columns():
    for forbidden in ("Agent_name", "Full_log", "Content", "Url", "Command", "Filename", "Path", "From"):
        assert forbidden not in USECOLS


def test_spedia_aggregation_values(tmp_path):
    d = lambda h, m=0: datetime(2025, 3, 4, h, m)  # a Tuesday
    rows = [
        spedia_row(1, "alice", d(9), "session", "Login", decoder="pam"),
        spedia_row(2, "alice", d(22), "session", "Login", decoder="pam"),            # after hours
        spedia_row(3, "alice", d(10), "session", "Login Failed", decoder="pam"),
        spedia_row(4, "alice", d(11), "email", "Email sent", To="x@dtaa.com;y@gmail.com", Attachments="2", Size="500"),
        spedia_row(5, "alice", d(11, 5), "email", "Email sent", To="x@dtaa.com", Attachments="0", Size="100"),
        spedia_row(6, "alice", d(12), "http", "URL accedida"),
        spedia_row(7, "alice", d(23), "http", "URL accedida", anomaly=1),
        spedia_row(8, "alice", d(12), "device", "Connect"), spedia_row(9, "alice", d(13), "device", "Disconnect"),
        spedia_row(10, "alice", d(14), "file", "File accessed"),
        spedia_row(11, "alice", d(15), "file", "File modified", decoder="syscheck_integrity_changed"),
        spedia_row(12, "alice", d(16), "command", "Command executed", decoder="auditd"),
    ]
    df, st = run(SpediaAdapter(), write_csv(tmp_path / "s.csv", rows))
    assert len(df) == 1
    r = df.iloc[0]
    assert (r.logon_count, r.after_hours_logons, r.failed_logon_count) == (2, 1, 1)
    assert (r.email_count, r.email_external_count, r.email_attachment_count, r.email_total_bytes) == (2, 1, 2, 600)
    assert (r.http_request_count, r.http_after_hours_count) == (2, 1)
    assert r.removable_device_events == 2 and r.file_access_count == 1 and r.file_integrity_event_count == 1
    assert r.command_exec_count == 1
    assert r.event_count == 12 and r.anomalous_event_count == 1
    assert r.after_hours_event_count == 2          # 22:00 login and 23:00 http
    assert np.isnan(r.total_session_duration) and np.isnan(r.file_copied_removable)  # unavailable != 0
    assert r.first_event_at == d(9) and r.last_event_at == d(23)


def test_chunking_does_not_change_result(tmp_path):
    from tests.helpers import make_spedia_csv
    p = make_spedia_csv(tmp_path / "s.csv", days=6)
    a, _ = run(SpediaAdapter(), p, chunk=1)
    b, _ = run(SpediaAdapter(), p, chunk=7)
    c, _ = run(SpediaAdapter(), p, chunk=100000)
    pd.testing.assert_frame_equal(a, b); pd.testing.assert_frame_equal(a, c)


def test_duplicates_missing_values_and_bad_rows_are_counted(tmp_path):
    d = datetime(2025, 3, 4, 9)
    rows = [
        spedia_row(1, "alice", d, "http", "URL accedida"),
        spedia_row(1, "alice", d, "http", "URL accedida"),              # duplicate id
        spedia_row(2, "", d, "http", "URL accedida"),                   # missing user
        spedia_row(3, "alice", d, "weird", "Whatever"),                 # unknown type
        spedia_row(4, "alice", d, "http", "URL accedida"),
    ]
    rows.append({**rows[0], "id": "id-5", "Timestamp": "not-a-date"})   # bad timestamp
    df, st = run(SpediaAdapter(), write_csv(tmp_path / "s.csv", rows))
    assert st.rows_read == 6 and st.rows_accepted == 2
    assert dict(st.rejected) == {"duplicate_event_id": 1, "bad_timestamp": 1, "missing_user": 1,
                                 "unrecognised_event_type": 1}
    assert df.iloc[0].http_request_count == 2


def test_weekend_rule_is_configurable(tmp_path):
    sat = datetime(2025, 3, 8, 10)   # Saturday, in business hours
    p = write_csv(tmp_path / "s.csv", [spedia_row(1, "alice", sat, "http", "URL accedida")])
    off, _ = run(SpediaAdapter(), p, BusinessHours(8, 18, False))
    on, _ = run(SpediaAdapter(), p, BusinessHours(8, 18, True))
    assert off.iloc[0].http_after_hours_count == 0 and on.iloc[0].http_after_hours_count == 1


def test_timestamps_and_identity_preserved_across_days(tmp_path):
    rows = [spedia_row(1, "root(uid=0)", datetime(2025, 3, 4, 23, 59, 59), "http", "URL accedida"),
            spedia_row(2, "root", datetime(2025, 3, 5, 0, 0, 1), "http", "URL accedida")]
    df, _ = run(SpediaAdapter(), write_csv(tmp_path / "s.csv", rows))
    assert df.user_id.tolist() == ["root", "root"]
    assert [str(x) for x in df["date"]] == ["2025-03-04", "2025-03-05"]


def test_cert_adapter_documented_layout(tmp_path):
    (tmp_path / "logon.csv").write_text("id,date,user,pc,activity\nL1,03/04/2010 09:00:00,DTAA/ACM1,PC1,Logon\n"
                                        "L2,03/04/2010 22:30:00,DTAA/ACM1,PC1,Logon\nL3,03/04/2010 23:00:00,DTAA/ACM1,PC1,Logoff\n")
    (tmp_path / "device.csv").write_text("id,date,user,pc,activity\nD1,03/04/2010 10:00:00,ACM1,PC1,Connect\n")
    (tmp_path / "email.csv").write_text(
        "id,date,user,pc,to,cc,bcc,from,size,attachments,content\n"
        f"E1,03/04/2010 11:00:00,ACM1,PC1,a@dtaa.com;b@gmail.com,,,x@dtaa.com,1200,2,{SECRET}\n")
    (tmp_path / "http.csv").write_text(f"id,date,user,pc,url,content\nH1,03/04/2010 12:00:00,ACM1,PC1,http://x,{SECRET}\n")
    ad = CertR42Adapter()
    df, st = run(ad, tmp_path, BusinessHours(8, 18, True))
    assert st.missing_sources == ["file.csv"]
    r = df.iloc[0]
    assert df.user_id.tolist() == ["acm1"] and (r.logon_count, r.after_hours_logons) == (2, 1)
    assert (r.removable_device_events, r.email_external_count, r.email_attachment_count, r.http_request_count) == (1, 1, 2, 1)
    assert np.isnan(r.anomalous_event_count)                 # no event-level labels in CERT
    assert np.isnan(r.command_exec_count) and np.isnan(r.file_copied_removable)


def test_file_fingerprint_changes_with_content(tmp_path):
    p = tmp_path / "a.csv"; p.write_text("x"); f1 = file_fingerprint([p]); p.write_text("y")
    assert f1 != file_fingerprint([p])
