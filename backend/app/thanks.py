"""감사 메일 승인 API (/thanks).

초안은 DB의 mail_drafts(mail_type='thanks')를 씁니다. 먼저 실행 (저장소 루트):
    python backend/thanks_mail/build_thanks.py
    python backend/db/load.py

상태 계산·승인·취소는 backend/app/mail_approvals.py 공통 함수를 씁니다.
실제 메일은 보내지 않고 승인 상태만 기록합니다.
"""
import json
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app import mail_approvals as ma

router = APIRouter()
MAIL_TYPE = "thanks"


class ApproveBody(BaseModel):
    mode: Literal["now", "scheduled"]
    scheduledAt: Optional[str] = None   # 'YYYY-MM-DD HH:MM' (mode='scheduled' 일 때 필수)
    excludedEmails: list[str] = []


def _drop_none(d):
    return {k: v for k, v in d.items() if v is not None}


def _summary(event, rows, now):
    s = ma.event_state(rows, now)
    return _drop_none({
        "eventId": event["event_id"], "eventName": event["event_name"], "eventDate": event["event_date"],
        "draftCount": s["draftCount"], "excludedCount": s["excludedCount"], "status": s["status"],
        "sendBy": s.get("sendBy"),
        "sendByPassed": (now[:16] > s["sendBy"]) if s.get("sendBy") else None,
        "scheduledAt": s.get("scheduledAt"), "sentAt": s.get("sentAt"),
    })


def _event(con, event_id):
    ev = con.execute("SELECT event_id, event_name, event_date FROM events WHERE event_id = ?", [event_id]).fetchone()
    if ev is None:
        raise HTTPException(404, f"행사 {event_id} 가 없습니다.")
    return dict(ev)


def _detail(con, event_id, now):
    ev = _event(con, event_id)
    rows = ma.load_rows(con, MAIL_TYPE, event_id)
    out = _summary(ev, rows, now)
    recipients = []
    for r in rows:
        item = ma.recipient(r, now)
        extra = json.loads(r["extra"]) if r["extra"] else {}
        item["surveyIncluded"] = extra.get("survey_included") == "Y"
        recipients.append(item)
    out["recipients"] = recipients
    return out


@router.get("/thanks")
def thanks_list():
    now = ma.now_str()
    con = ma.open_db()
    try:
        events = [dict(e) for e in con.execute("SELECT event_id, event_name, event_date FROM events ORDER BY event_id")]
        by_event = {}
        for r in ma.load_rows(con, MAIL_TYPE):
            by_event.setdefault(r["event_id"], []).append(r)
        return [_summary(e, by_event.get(e["event_id"], []), now) for e in events]
    finally:
        con.close()


@router.get("/thanks/{event_id}")
def thanks_detail(event_id: str):
    con = ma.open_db()
    try:
        return _detail(con, event_id, ma.now_str())
    finally:
        con.close()


@router.post("/thanks/{event_id}/approve")
def thanks_approve(event_id: str, body: ApproveBody):
    con = ma.open_db()
    try:
        _event(con, event_id)
        now = ma.now_str()
        warnings = ma.approve(con, MAIL_TYPE, event_id, body.mode, body.scheduledAt, body.excludedEmails, now)
        out = _detail(con, event_id, now)
        out.pop("recipients")
        out["warnings"] = warnings
        return out
    finally:
        con.close()


@router.post("/thanks/{event_id}/cancel")
def thanks_cancel(event_id: str):
    con = ma.open_db()
    try:
        _event(con, event_id)
        now = ma.now_str()
        ma.cancel(con, MAIL_TYPE, event_id, now)
        out = _detail(con, event_id, now)
        out.pop("recipients")
        return out
    finally:
        con.close()
