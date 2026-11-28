"""data/processed/*.csv 7개와 감사 메일 초안(out/thanks_mails.csv)을 SQLite DB에 넣습니다.

실행 (저장소 루트에서, build_profile.py · build_thanks.py 다음에):
    python backend/db/load.py [--csv-dir data/processed] [--thanks-csv out/thanks_mails.csv]

실행할 때마다 schema.sql 적용 → 표 비우기 → 다시 넣기를 하나의 트랜잭션으로 처리합니다.
중간에 실패하면 전부 되돌려 DB는 실행 전 상태 그대로 남습니다.

메일 표:
- mail_drafts 는 mail_type='thanks' 행만 지우고 다시 넣습니다 (custom·content 행은 그대로).
  out/thanks_mails.csv 가 없으면 안내만 하고 mail_drafts 는 건드리지 않습니다.
- mail_approvals(승인 기록)는 어떤 경우에도 비우거나 다시 만들지 않습니다.
"""
import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from conn import ROOT, connect, db_path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
# schema.sql 주석의 넣는 순서 (외래 키 때문에 참조되는 표가 먼저)
TABLES = ["events", "companies", "customers", "participation", "surveys", "interactions", "contents"]
# 메일 표(mail_drafts, mail_approvals)는 TABLES 에 넣지 않음 → 아래 "표 비우기"에서 지워지지 않음.
# mail_approvals 는 이 파일 어디에서도 DELETE/DROP 하지 않음.
THANKS_CSV = ROOT / "out" / "thanks_mails.csv"
THANKS_COLS = ["event_id", "email", "name", "company", "title", "consent", "survey_included",
               "sender", "send_by", "subject", "body"]
DRAFT_COLS = ["draft_id", "mail_type", "event_id", "email", "name", "company", "title", "sender",
              "subject", "body", "send_by", "body_hash", "extra", "created_at"]


def body_hash(subject, body):
    """승인 후 제목·본문이 바뀌었는지 보는 값. 제목도 포함 (제목만 바뀌어도 다시 승인)."""
    return hashlib.sha256(f"{subject or ''}\n{body or ''}".encode("utf-8")).hexdigest()


def convert(value):
    """빈 값 → None, True/False → 1/0. 나머지는 문자열 그대로 (INTEGER 열은 SQLite가 숫자로 바꿈)."""
    if value is None or value.strip() == "":
        return None
    if value == "True":
        return 1
    if value == "False":
        return 0
    return value


def read_csv(path):
    # utf-8-sig: 첫 열 이름 앞의 BOM 제거
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = [{c: convert(r[c]) for c in cols} for r in reader]
    return cols, rows


def filter_participation(rows):
    """테스트 행사 행과 이메일 빈 행을 뺌. 둘 다 해당하면 테스트로 셈."""
    kept, n_test, n_no_email = [], 0, 0
    for r in rows:
        if r["is_test"] == 1:
            n_test += 1
        elif r["email"] is None:
            n_no_email += 1
        else:
            kept.append(r)
    return kept, n_test, n_no_email


def read_all(csv_dir):
    data = {}
    for t in TABLES:
        path = csv_dir / f"{t}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} 가 없습니다. build_profile.py 를 먼저 실행해 주세요.")
        data[t] = read_csv(path)
    return data


def read_thanks(path):
    """out/thanks_mails.csv → mail_drafts 행 목록. 파일이 없으면 None."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in THANKS_COLS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: 필요한 열이 없습니다: {missing}. build_thanks.py 를 다시 실행해 주세요.")
        src = list(reader)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows, seen = [], set()
    for r in src:
        v = {c: convert(r[c]) for c in THANKS_COLS}
        if not v["event_id"] or not v["email"]:
            raise ValueError(f"{path}: event_id 또는 email 이 빈 행이 있습니다.")
        draft_id = f"thanks:{v['event_id']}:{v['email']}"
        if draft_id in seen:
            raise ValueError(f"{path}: 같은 초안이 두 번 있습니다: {draft_id}")
        seen.add(draft_id)
        extra = {"survey_included": v["survey_included"], "consent": v["consent"]}
        rows.append({"draft_id": draft_id, "mail_type": "thanks", "event_id": v["event_id"], "email": v["email"],
                     "name": v["name"], "company": v["company"], "title": v["title"], "sender": v["sender"],
                     "subject": r["subject"], "body": r["body"], "send_by": v["send_by"],
                     "body_hash": body_hash(r["subject"], r["body"]),
                     "extra": json.dumps(extra, ensure_ascii=False), "created_at": now})
    return rows


def load(con, data, thanks):
    con.executescript("BEGIN;\n" + SCHEMA_PATH.read_text(encoding="utf-8"))
    # events 를 비웠다 다시 넣는 동안 mail_drafts(custom 등)의 event_id 외래 키가 막지 않도록 COMMIT 때 검사
    con.execute("PRAGMA defer_foreign_keys = ON")
    for t in TABLES:
        table_cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        if table_cols != data[t][0]:
            raise ValueError(f"{t}: CSV 열 이름이 표와 다릅니다.\n  표 : {table_cols}\n  CSV: {data[t][0]}")
    for t in reversed(TABLES):
        con.execute(f"DELETE FROM {t}")
    for t in TABLES:
        cols, rows = data[t]
        sql = f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        try:
            con.executemany(sql, ([r[c] for c in cols] for r in rows))
        except sqlite3.Error as e:
            raise sqlite3.Error(f"{t} 넣기 실패: {e}") from e
    if thanks is not None:
        con.execute("DELETE FROM mail_drafts WHERE mail_type = 'thanks'")
        sql = f"INSERT INTO mail_drafts ({', '.join(DRAFT_COLS)}) VALUES ({', '.join('?' * len(DRAFT_COLS))})"
        try:
            con.executemany(sql, ([r[c] for c in DRAFT_COLS] for r in thanks))
        except sqlite3.Error as e:
            raise sqlite3.Error(f"mail_drafts(thanks) 넣기 실패: {e}") from e
    try:
        con.execute("COMMIT")
    except sqlite3.IntegrityError as e:
        raise sqlite3.Error(f"외래 키 검사 실패 (mail_drafts 의 event_id 가 events 에 없을 수 있음): {e}") from e


def main():
    ap = argparse.ArgumentParser(description="data/processed/*.csv → SQLite")
    ap.add_argument("--csv-dir", default=str(ROOT / "data" / "processed"), help="CSV 폴더 (기본 data/processed)")
    ap.add_argument("--thanks-csv", default=str(THANKS_CSV), help="감사 메일 초안 CSV (기본 out/thanks_mails.csv)")
    a = ap.parse_args()

    try:
        data = read_all(Path(a.csv_dir))
        thanks = read_thanks(Path(a.thanks_csv))
    except (OSError, KeyError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    cols, rows = data["participation"]
    kept, n_test, n_no_email = filter_participation(rows)
    data["participation"] = (cols, kept)
    print(f"participation 제외: 테스트 행사 {n_test}행, 이메일 빈 행 {n_no_email}행 (합계 {n_test + n_no_email}행)")

    if thanks is None:
        print(f"안내: {a.thanks_csv} 가 없어 감사 메일 초안은 건너뜁니다 (기존 thanks 초안은 그대로 둠). "
              "build_thanks.py 를 실행한 뒤 다시 실행하면 들어갑니다.")

    path = db_path()
    con = connect(path)
    con.isolation_level = None  # 트랜잭션을 직접 관리
    try:
        load(con, data, thanks)
    except Exception as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        print(f"오류: {e}\n되돌렸습니다. DB는 실행 전 상태 그대로입니다.", file=sys.stderr)
        con.close()
        return 1

    print("넣은 행 수")
    for t in TABLES:
        print(f"  {t:<14}{con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>5}")
    print("메일 표 (현재 행 수)")
    for mt, n in con.execute("SELECT mail_type, COUNT(*) FROM mail_drafts GROUP BY mail_type ORDER BY mail_type"):
        print(f"  mail_drafts {mt:<8}{n:>5}")
    print(f"  mail_approvals{con.execute('SELECT COUNT(*) FROM mail_approvals').fetchone()[0]:>5}  (비우지 않음)")
    con.close()
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"DB: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
