"""data/processed/*.csv 7개를 SQLite DB에 넣습니다.

실행 (저장소 루트에서, build_profile.py 다음에):
    python backend/db/load.py [--csv-dir data/processed]

실행할 때마다 schema.sql 적용 → 표 비우기 → 다시 넣기를 하나의 트랜잭션으로 처리합니다.
중간에 실패하면 전부 되돌려 DB는 실행 전 상태 그대로 남습니다.
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from conn import ROOT, connect, db_path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
# schema.sql 주석의 넣는 순서 (외래 키 때문에 참조되는 표가 먼저)
TABLES = ["events", "companies", "customers", "participation", "surveys", "interactions", "contents"]


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


def load(con, data):
    con.executescript("BEGIN;\n" + SCHEMA_PATH.read_text(encoding="utf-8"))
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
    con.execute("COMMIT")


def main():
    ap = argparse.ArgumentParser(description="data/processed/*.csv → SQLite")
    ap.add_argument("--csv-dir", default=str(ROOT / "data" / "processed"), help="CSV 폴더 (기본 data/processed)")
    a = ap.parse_args()

    try:
        data = read_all(Path(a.csv_dir))
    except (OSError, KeyError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    cols, rows = data["participation"]
    kept, n_test, n_no_email = filter_participation(rows)
    data["participation"] = (cols, kept)
    print(f"participation 제외: 테스트 행사 {n_test}행, 이메일 빈 행 {n_no_email}행 (합계 {n_test + n_no_email}행)")

    path = db_path()
    con = connect(path)
    con.isolation_level = None  # 트랜잭션을 직접 관리
    try:
        load(con, data)
    except Exception as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        print(f"오류: {e}\n되돌렸습니다. DB는 실행 전 상태 그대로입니다.", file=sys.stderr)
        con.close()
        return 1

    print("넣은 행 수")
    for t in TABLES:
        print(f"  {t:<14}{con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>5}")
    con.close()
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"DB: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
