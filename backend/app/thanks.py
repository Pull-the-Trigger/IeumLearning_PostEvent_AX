"""감사 메일 승인 API (/thanks).

초안은 DB의 mail_drafts(mail_type='thanks')를 씁니다. 먼저 실행 (저장소 루트):
    python backend/thanks_mail/build_thanks.py
    python backend/db/load.py

상태 계산·승인·취소는 backend/app/mail_approvals.py 공통 함수를 씁니다.
실제 메일은 보내지 않고 승인 상태만 기록합니다.

문안 수정 (/thanks/{event_id}/template): 행사별 제목·본문·설문 요청 문단·링크를 thanks_settings 에 저장하고
그 행사 초안 전체를 backend/thanks_mail/build_thanks.py 의 render_with_settings 로 다시 만듭니다.
body_hash 가 바뀌므로 기존 승인은 자동으로 무효가 됩니다. 발송 완료 행사는 고칠 수 없습니다(409).
"""
import json
import sqlite3
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app import mail_approvals as ma
from backend.db.conn import body_hash
from backend.thanks_mail import build_thanks as bt

router = APIRouter()
MAIL_TYPE = "thanks"


class ApproveBody(BaseModel):
    mode: Literal["now", "scheduled"]
    scheduledAt: Optional[str] = None   # 'YYYY-MM-DD HH:MM' (mode='scheduled' 일 때 필수)
    excludedEmails: list[str] = []


class TemplateBody(BaseModel):
    subjectTemplate: str
    bodyTemplate: str
    surveyAskBlock: str
    slidesUrl: str
    surveyUrl: str


# thanks_settings 열 ↔ 화면 필드 이름
SETTING_KEYS = {"subject_template": "subjectTemplate", "body_template": "bodyTemplate",
                "survey_ask_block": "surveyAskBlock", "slides_url": "slidesUrl", "survey_url": "surveyUrl"}


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


# ---- 문안 수정 ----

def _saved_settings(con, event_id):
    """thanks_settings 의 그 행사 줄 (없으면 None). 표가 아직 없으면(load.py 전) 없는 것으로 봄."""
    try:
        row = con.execute("SELECT * FROM thanks_settings WHERE event_id = ?", [event_id]).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _template_out(con, event_id):
    saved = _saved_settings(con, event_id)
    s = saved or bt.default_settings(event_id)
    thanks_block, signature = bt.fixed_parts()
    out = {"eventId": event_id, "customized": saved is not None}
    out.update({camel: s[col] for col, camel in SETTING_KEYS.items()})
    if saved:
        out["updatedAt"] = saved["updated_at"]
    out["placeholders"] = {SETTING_KEYS[f]: v for f, v in bt.PLACEHOLDERS.items()}
    out["fixed"] = {"surveyThanksBlock": thanks_block, "signature": signature}
    return out


def _rebuild(con, event, rows, settings):
    """그 행사 감사 메일 초안 전부를 settings 로 다시 만들어 UPDATE. 돌려주는 값: lint 경고 목록."""
    warnings = []
    for r in rows:
        extra = json.loads(r["extra"]) if r["extra"] else {}
        subject, body = bt.render_with_settings(
            settings, name=r["name"], title=r["title"], event_name=event["event_name"],
            event_date=event["event_date"], include_survey=extra.get("survey_included") == "Y")
        con.execute("UPDATE mail_drafts SET subject = ?, body = ?, body_hash = ? WHERE draft_id = ?",
                    [subject, body, body_hash(subject, body), r["draft_id"]])
        warnings += bt.lint(subject + "\n" + body)
    return sorted(set(warnings))


def _change_template(event_id, settings):
    """settings 가 None 이면 저장된 줄을 지우고 기본 문안으로. 하나의 트랜잭션."""
    con = ma.open_db()
    try:
        event = _event(con, event_id)
        now = ma.now_str()
        con.execute("BEGIN IMMEDIATE")
        try:
            rows = ma.load_rows(con, MAIL_TYPE, event_id)
            if not rows:
                raise HTTPException(404, f"{event_id} 의 감사 메일 초안이 없습니다.")
            if ma.event_state(rows, now)["status"] == "sent":
                raise HTTPException(409, "발송 완료된 행사는 문안을 고칠 수 없습니다.")
            valid_before = {r["draft_id"] for r in rows if r.get("a_status") and r["a_body_hash"] == r["body_hash"]}
            try:
                if settings is None:
                    con.execute("DELETE FROM thanks_settings WHERE event_id = ?", [event_id])
                    used = bt.default_settings(event_id)
                else:
                    con.execute(
                        "INSERT INTO thanks_settings (event_id, subject_template, body_template, survey_ask_block,"
                        " slides_url, survey_url, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
                        " ON CONFLICT(event_id) DO UPDATE SET subject_template = excluded.subject_template,"
                        " body_template = excluded.body_template, survey_ask_block = excluded.survey_ask_block,"
                        " slides_url = excluded.slides_url, survey_url = excluded.survey_url,"
                        " updated_at = excluded.updated_at",
                        [event_id, *[settings[c] for c in SETTING_KEYS], now])
                    used = settings
            except sqlite3.OperationalError as e:
                raise HTTPException(503, f"thanks_settings 표를 쓰지 못했습니다 ({e}). "
                                         "python backend/db/load.py 를 먼저 실행해 주세요.")
            warnings = _rebuild(con, event, rows, used)
            after = ma.load_rows(con, MAIL_TYPE, event_id)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        invalidated = sum(r["draft_id"] in valid_before and r["a_body_hash"] != r["body_hash"] for r in after)
        out = _template_out(con, event_id)
        out.update({"status": ma.event_state(after, now)["status"], "invalidatedCount": invalidated,
                    "warnings": warnings})
        return out
    finally:
        con.close()


@router.get("/thanks/{event_id}/template")
def thanks_template(event_id: str):
    con = ma.open_db()
    try:
        _event(con, event_id)
        return _template_out(con, event_id)
    finally:
        con.close()


@router.post("/thanks/{event_id}/template")
def thanks_template_save(event_id: str, body: TemplateBody):
    settings = {col: getattr(body, camel).replace("\r\n", "\n") for col, camel in SETTING_KEYS.items()}
    settings["slides_url"], settings["survey_url"] = settings["slides_url"].strip(), settings["survey_url"].strip()
    errors = bt.validate_settings(settings)
    if errors:
        raise HTTPException(400, " / ".join(errors))
    return _change_template(event_id, settings)


@router.post("/thanks/{event_id}/template/reset")
def thanks_template_reset(event_id: str):
    return _change_template(event_id, None)
