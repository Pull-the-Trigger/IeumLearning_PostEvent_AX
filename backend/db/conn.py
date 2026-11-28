"""SQLite 연결.

DB 파일 위치는 환경변수 → 루트 .env 의 DB_PATH 순서로 찾고, 없으면 data/processed/ieum.db.
상대 경로는 저장소 루트 기준입니다. 연결할 때마다 외래 키를 켭니다.
"""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
DEFAULT_DB_PATH = ROOT / "data" / "processed" / "ieum.db"


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


def db_path():
    value = read_env("DB_PATH")
    if not value:
        return DEFAULT_DB_PATH
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


def connect(path=None):
    """DB에 연결. 행은 sqlite3.Row(열 이름으로 꺼낼 수 있음)로 돌려줌."""
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
