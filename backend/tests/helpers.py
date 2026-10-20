"""Small deterministic fixtures. SPEDIA-shaped CSVs are synthetic: they exercise code paths and carry
no claim about real-data behaviour."""
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

SPEDIA_COLUMNS = ["id", "Agent_name", "User", "Timestamp", "Decoder_name", "Description", "Full_log",
                  "Content", "Url", "To", "Cc", "Bcc", "From", "Attachments", "Size", "Size_before",
                  "Size_after", "Filename", "Path", "Command", "Level", "Activity", "Action", "Anomaly"]
SECRET = "SECRET_BODY_TEXT"


def spedia_row(i, user, ts, activity, action, decoder="cert", anomaly=0, agent=None, **kw):
    row = {c: "" for c in SPEDIA_COLUMNS}
    row.update(id=f"id-{i}", User=user, Timestamp=ts.strftime("%Y-%m-%d %H:%M:%S.000"), Activity=activity,
               Action=action, Decoder_name=decoder, Anomaly=str(anomaly),
               Agent_name=agent or ("host_simulation" if anomaly == 0 else "host_deadbeef"),
               Full_log=SECRET, Content=SECRET, Url="http://secret.example/" + SECRET)
    row.update(kw)
    return row


def write_csv(path: Path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SPEDIA_COLUMNS)
        w.writeheader(); w.writerows(rows)
    return path


def make_spedia_csv(path: Path, days: int = 20, start: date = date(2025, 3, 3), spike_last_day: bool = True):
    """Two users ('alice','bob'); steady daily routine; alice spikes (many after-hours emails/USB) on the last day."""
    rows, n = [], 0
    def add(*a, **k):
        nonlocal n; n += 1; rows.append(spedia_row(n, *a, **k))
    for d in range(days):
        day = datetime.combine(start + timedelta(days=d), datetime.min.time())
        last = spike_last_day and d == days - 1
        for user in ("alice", "bob"):
            for h in (9, 10, 11):
                add(user, day + timedelta(hours=h), "http", "URL accedida", Url="http://x.test/a")
            add(user, day + timedelta(hours=9), "session", "Login", decoder="pam")
            add(user, day + timedelta(hours=17), "session", "Logoff", decoder="pam")
            add(user, day + timedelta(hours=13), "email", "Email sent", To="peer@dtaa.com", Attachments="0", Size="1000")
            add(user, day + timedelta(hours=14), "file", "File accessed", Filename="f.txt")
            if user == "alice" and last:
                for k in range(15):
                    add(user, day + timedelta(hours=23, minutes=k), "email", "Email sent", anomaly=1,
                        To="a@gmail.com;b@dtaa.com", Attachments="3", Size="50000")
                    add(user, day + timedelta(hours=2, minutes=k), "device", "Connect", anomaly=1)
    return write_csv(path, rows)
