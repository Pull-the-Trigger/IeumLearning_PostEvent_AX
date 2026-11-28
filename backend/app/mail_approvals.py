"""메일 승인 공통 함수 (감사 메일·맞춤 메일·맞춤 콘텐츠 모두 사용, mail_type 을 인자로 받음).

표: mail_drafts(초안) + mail_approvals(승인 기록). backend/db/schema.sql 참고.
실제 메일은 보내지 않고 승인 상태만 기록합니다.

행사 단위 상태 (화면 값과 같음)
  draft      초안 없음
  review     초안은 있지만 유효한 승인이 없음 (승인 기록 없음, 또는 승인 후 제목·본문이 바뀜 = 승인 무효)
  scheduled  예약 시각이 아직 안 옴
  sent       지금 발송으로 승인했거나 예약 시각이 지남.
             이미 보낸 메일은 되돌릴 수 없으므로 그 뒤 초안이 바뀌어도 sent 유지 (받는 사람별 approvalInvalid 로만 표시)

시간은 Asia/Seoul 기준 'YYYY-MM-DD HH:MM:SS' 문자열 (문자열 비교 = 시각 비교).
현재 시각은 backend.db.conn.now() (DEMO_TODAY 가 있으면 날짜만 그 날로 바뀜).
"""
import re
import sqlite3
from datetime import datetime

from fastapi import HTTPException

from backend.db import conn
from backend.db.conn import connect

SCHEDULE_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def now_str():
    return conn.now().strftime("%Y-%m-%d %H:%M:%S")


def norm_email(s):
    return (s or "").strip().lower()


def prefix(mail_type, event_id):
    """그 행사의 draft_id 앞부분. 승인 기록은 이것으로 찾음 (초안이 사라진 승인 기록도 같이 잡힘)."""
    return f"{mail_type}:{event_id}:"


def _like(mail_type, event_id):
    p = prefix(mail_type, event_id)
    return p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def open_db():
    """요청마다 새로 연결 (SQLite 연결은 스레드끼리 같이 쓰지 않음). 트랜잭션은 직접 관리."""
    con = connect()
    con.isolation_level = None
    try:
        con.execute("SELECT 1 FROM mail_drafts LIMIT 1")
        con.execute("SELECT 1 FROM mail_approvals LIMIT 1")
    except sqlite3.OperationalError as e:
        con.close()
        raise HTTPException(503, f"메일 표를 읽지 못했습니다 ({e}). python backend/db/load.py 를 먼저 실행해 주세요.")
    return con


def load_rows(con, mail_type, event_id=None):
    """초안 + 승인 기록. event_id 가 없으면 그 종류의 전체 초안."""
    sql = """
        SELECT d.*, a.status AS a_status, a.body_hash AS a_body_hash,
               a.approved_at, a.scheduled_at, a.sent_at
        FROM mail_drafts d
        LEFT JOIN mail_approvals a ON a.draft_id = d.draft_id
        WHERE d.mail_type = ?
    """
    args = [mail_type]
    if event_id is not None:
        sql += " AND d.event_id = ?"
        args.append(event_id)
    return [dict(r) for r in con.execute(sql + " ORDER BY d.event_id, d.email", args)]


def row_state(row, now):
    """받는 사람별 (approvalStatus, approvalInvalid)."""
    st = row.get("a_status")
    if st is None:
        return "none", False
    invalid = row["a_body_hash"] != row["body_hash"]
    if st == "scheduled" and row["scheduled_at"] and row["scheduled_at"] <= now:
        st = "sent"
    return st, invalid


def event_state(rows, now):
    """한 행사의 초안 행들 → 행사 요약."""
    if not rows:
        return {"status": "draft", "draftCount": 0, "excludedCount": 0}
    states = [row_state(r, now) for r in rows]
    send_by = min((r["send_by"] for r in rows if r["send_by"]), default=None)
    excluded = sum(s == "excluded" for s, _ in states)
    out = {"draftCount": len(rows), "excludedCount": excluded, "sendBy": send_by}

    sent = [r for r, (s, _) in zip(rows, states) if s == "sent"]
    if sent:
        out["status"] = "sent"
        out["sentAt"] = min(r["sent_at"] or r["scheduled_at"] for r in sent)
        return out
    if any(s == "none" or invalid for s, invalid in states):
        out["status"] = "review"
        return out
    out["status"] = "scheduled"
    out["scheduledAt"] = min((r["scheduled_at"] for r in rows if r["scheduled_at"]), default=None)
    return out


def recipient(row, now):
    st, invalid = row_state(row, now)
    return {"draftId": row["draft_id"], "email": row["email"], "name": row["name"], "company": row["company"],
            "title": row["title"], "subject": row["subject"], "body": row["body"], "sender": row["sender"],
            "approvalStatus": st, "approvalInvalid": invalid}


def approve(con, mail_type, event_id, mode, scheduled_at=None, excluded_emails=(), now=None):
    """행사 단위 승인. 그 행사의 기존 승인 기록은 새 승인으로 덮어씀. 돌려주는 값: warnings 목록."""
    now = now or now_str()
    if mode not in ("now", "scheduled"):
        raise HTTPException(400, "mode 는 'now' 또는 'scheduled' 입니다.")
    warnings = []
    con.execute("BEGIN IMMEDIATE")
    try:
        rows = load_rows(con, mail_type, event_id)
        if not rows:
            raise HTTPException(404, f"{event_id} 의 초안이 없습니다.")
        state = event_state(rows, now)
        if state["status"] == "sent":
            raise HTTPException(409, "이미 발송된 메일입니다. 다시 승인할 수 없습니다.")

        excluded = {norm_email(e) for e in excluded_emails or []}
        unknown = sorted(excluded - {r["email"] for r in rows})
        if unknown:
            raise HTTPException(400, f"이 행사 초안에 없는 이메일입니다: {', '.join(unknown)}")
        if len(excluded) == len(rows):
            raise HTTPException(400, "모든 받는 사람을 제외하면 보낼 메일이 없습니다.")

        sched = None
        if mode == "scheduled":
            if not scheduled_at or not SCHEDULE_FORMAT.fullmatch(scheduled_at.strip()):
                raise HTTPException(400, "scheduledAt 은 'YYYY-MM-DD HH:MM' 형식으로 보내 주세요.")
            try:
                datetime.strptime(scheduled_at.strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                raise HTTPException(400, f"없는 날짜·시각입니다: {scheduled_at}")
            sched = scheduled_at.strip() + ":00"
            if sched <= now:
                raise HTTPException(400, f"예약 시각({scheduled_at})이 지금({now[:16]})보다 과거입니다.")
            if state.get("sendBy") and sched > state["sendBy"] + ":00":
                warnings.append(f"예약 시각({scheduled_at})이 발송 기한({state['sendBy']})보다 늦습니다.")

        con.execute("DELETE FROM mail_approvals WHERE draft_id LIKE ? ESCAPE '\\'", [_like(mail_type, event_id)])
        for r in rows:
            if r["email"] in excluded:
                values = ("excluded", None, None)
            elif mode == "now":
                values = ("sent", None, now)
            else:
                values = ("scheduled", sched, None)
            con.execute(
                "INSERT INTO mail_approvals (draft_id, status, body_hash, approved_at, scheduled_at, sent_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [r["draft_id"], values[0], r["body_hash"], now, values[1], values[2]])
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return warnings


def cancel(con, mail_type, event_id, now=None):
    """발송 예정(예약 시각 전)일 때만 그 행사 승인 기록을 지움."""
    now = now or now_str()
    con.execute("BEGIN IMMEDIATE")
    try:
        rows = load_rows(con, mail_type, event_id)
        status = event_state(rows, now)["status"]
        if status == "sent":
            raise HTTPException(409, "발송된 메일은 취소할 수 없습니다.")
        if status != "scheduled":
            raise HTTPException(409, "취소할 발송 예약이 없습니다.")
        con.execute("DELETE FROM mail_approvals WHERE draft_id LIKE ? ESCAPE '\\'", [_like(mail_type, event_id)])
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
