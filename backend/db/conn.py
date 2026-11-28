"""SQLite 연결.

DB 파일 위치는 환경변수 → 루트 .env 의 DB_PATH 순서로 찾고, 없으면 data/processed/ieum.db.
상대 경로는 저장소 루트 기준입니다. 연결할 때마다 외래 키를 켭니다.

기준일: today()/now() 는 DEMO_TODAY(YYYY-MM-DD, 시연용)가 있으면 그 날짜, 없으면 실제 오늘 (Asia/Seoul).
다른 코드에서: from backend.db.conn import today, now
"""
import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
DEFAULT_DB_PATH = ROOT / "data" / "processed" / "ieum.db"
TZ = ZoneInfo("Asia/Seoul")


def read_env(name):
    """환경변수 → .env 순서로 찾음. 없거나 빈 값이면 None."""
    if os.environ.get(name):
        return os.environ[name]
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == name:
            return v.strip().strip('"').strip("'") or None
    return None


def demo_today():
    """DEMO_TODAY 날짜 (date). 없거나 비면 None, 형식이 틀리면 ValueError."""
    value = read_env("DEMO_TODAY")
    if not value:
        return None
    try:
        if len(value) != 10:
            raise ValueError
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"DEMO_TODAY 형식이 틀렸습니다: {value!r}. "
            "YYYY-MM-DD 로 적거나 비워 두세요 (예: DEMO_TODAY=2026-07-09)."
        ) from None


def today():
    """기준일 (date). DEMO_TODAY 가 있으면 그 날짜, 없으면 실제 오늘 (Asia/Seoul)."""
    return demo_today() or datetime.now(TZ).date()


def now():
    """기준 시각 (Asia/Seoul, tz 포함). 날짜는 today(), 시·분·초는 실제 현재 시각."""
    return datetime.combine(today(), datetime.now(TZ).timetz())


def db_path():
    value = read_env("DB_PATH")
    if not value:
        return DEFAULT_DB_PATH
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


def body_hash(subject, body):
    """메일 초안 승인 확인용 값 sha256(subject + "\n" + body). 제목만 바뀌어도 달라짐 → 다시 승인."""
    return hashlib.sha256(f"{subject or ''}\n{body or ''}".encode("utf-8")).hexdigest()


def connect(path=None):
    """DB에 연결. 행은 sqlite3.Row(열 이름으로 꺼낼 수 있음)로 돌려줌."""
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
