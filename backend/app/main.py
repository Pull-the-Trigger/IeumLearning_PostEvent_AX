"""데이터 관리 화면용 조회 API (GET만).

실행 (저장소 루트에서, load.py 로 DB를 만든 뒤):
    uvicorn backend.app.main:app --reload

응답 필드 이름은 화면 타입(frontend/lib/data-management-data.ts)과 같은 camelCase 입니다.
현재 로그인·접근 제한이 없습니다. 로컬 개발·시연용이며 서버 배포 전 인증이 필요합니다.
"""
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.db.conn import connect, read_env

DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]
ADOPTION_LABEL = {"Y": "예", "REVIEW": "검토 중", "N": "아니오"}  # 설문 Q6 (화면 설문 선택지)
YES_NO_LABEL = {"Y": "예", "N": "아니오"}                         # 설문 Q7


def cors_origins():
    value = read_env("CORS_ORIGINS")
    origins = [o.strip() for o in value.split(",") if o.strip()] if value else []
    return origins or DEFAULT_CORS_ORIGINS


app = FastAPI(title="이음러닝 데이터 관리 API", description="데이터 관리 화면용 조회 API (GET만, 인증 없음 · 로컬 개발·시연용)")
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET"], allow_headers=["*"])


def query(sql):
    """요청마다 새로 연결해서 실행하고 닫음 (SQLite 연결은 스레드끼리 같이 쓰지 않음)."""
    con = connect()
    try:
        return [dict(r) for r in con.execute(sql)]
    except sqlite3.OperationalError as e:
        raise HTTPException(503, f"DB를 읽지 못했습니다 ({e}). python backend/db/load.py 를 먼저 실행해 주세요.")
    finally:
        con.close()


def to_bool(rows, *fields):
    for r in rows:
        for f in fields:
            r[f] = bool(r[f])
    return rows


def drop_none(d):
    return {k: v for k, v in d.items() if v is not None}


@app.get("/health")
def health():
    query("SELECT COUNT(*) FROM events")
    return {"status": "ok", "db": "ok"}


@app.get("/events")
def events():
    return query("""
        SELECT event_id AS eventId, event_name AS eventName, event_date AS eventDate, event_type AS eventType,
               applied_count AS appliedCount, attended_count AS attendedCount,
               thanks_mail_date AS thanksMailDate, survey_count AS surveyCount, note
        FROM events ORDER BY event_id
    """)


@app.get("/customers")
def customers():
    rows = query("""
        WITH counts AS (
            SELECT p.email, COUNT(*) AS applied, SUM(p.attended = 'Y') AS attended
            FROM participation p
            JOIN events e ON e.event_id = p.event_id   -- DB에 등록된 행사 기준
            GROUP BY p.email
        )
        SELECT c.email AS id, c.name, c.company, c.title, c.email,
               COALESCE(n.attended, 0) > 0 AS attended,
               COALESCE(c.consent, 'UNKNOWN') AS consent,
               COALESCE(n.attended, 0) AS attendanceCount,
               EXISTS (SELECT 1 FROM surveys s WHERE s.email = c.email) AS surveyResponded,
               co.industry_mid AS industry,
               CASE WHEN COALESCE(n.attended, 0) >= 2 THEN 'Y' ELSE 'N' END AS existingCustomer,
               c.first_event_id AS firstEventId, c.last_event_id AS lastEventId,
               COALESCE(n.applied, 0) AS appliedCount,
               COALESCE(n.attended, 0) AS attendedCount
        FROM customers c
        LEFT JOIN companies co ON co.company_key = c.company_key
        LEFT JOIN counts n ON n.email = c.email
        ORDER BY c.email
    """)
    # 설문 Q5(듣고 싶은 주제): 고객별로 최근 응답 순, 중복 제거
    topics = {}
    for t in query("""
        SELECT email, TRIM(q5_wanted_topic) AS topic FROM surveys
        WHERE email IS NOT NULL AND TRIM(COALESCE(q5_wanted_topic, '')) <> ''
        ORDER BY response_date DESC, survey_id DESC
    """):
        seen = topics.setdefault(t["email"], [])
        if t["topic"] not in seen:
            seen.append(t["topic"])
    for r in rows:
        r["interests"] = ", ".join(topics.get(r["email"], []))
    return to_bool(rows, "attended", "surveyResponded")


@app.get("/participation")
def participation():
    rows = query("""
        WITH attended AS (
            SELECT email, SUM(attended = 'Y') AS n FROM participation GROUP BY email
        )
        SELECT p.email AS id, p.name, p.company, p.title, p.email,
               p.attended = 'Y' AS attended,
               COALESCE(p.consent, 'UNKNOWN') AS consent,
               a.n AS attendanceCount,
               s.survey_id IS NOT NULL AS surveyResponded,
               p.pre_question AS preQuestion,
               i.memo AS interactionMemo,
               s.q4_helpful_content AS q4, s.q5_wanted_topic AS q5, s.q6_adoption AS q6, s.q7_contact_wish AS q7,
               p.event_id AS eventId, e.event_name AS eventName, p.note
        FROM participation p
        JOIN events e ON e.event_id = p.event_id
        JOIN attended a ON a.email = p.email
        LEFT JOIN surveys s ON s.event_id = p.event_id AND s.email = p.email        -- (행사, 이메일)당 최대 1건
        LEFT JOIN interactions i ON i.event_id = p.event_id AND i.email = p.email   -- (행사, 이메일)당 최대 1건
        ORDER BY p.event_id, p.source_row
    """)
    out = []
    for r in to_bool(rows, "attended", "surveyResponded"):
        answers = {"q4": r.pop("q4"), "q5": r.pop("q5"),
                   "q6": ADOPTION_LABEL.get(r.pop("q6")), "q7": YES_NO_LABEL.get(r.pop("q7"))}
        if r["surveyResponded"]:
            r["surveyAnswers"] = drop_none(answers)
        if r["interactionMemo"] is None:
            del r["interactionMemo"]
        out.append(r)
    return out


@app.get("/surveys")
def surveys():
    rows = query("""
        SELECT s.survey_id, s.event_id, e.event_name, s.response_date,
               s.q1_satisfaction, s.q2_helpfulness, s.q3_recommend, s.q4_helpful_content, s.q5_wanted_topic,
               s.q6_adoption, s.q7_contact_wish, s.email, s.matched
        FROM surveys s
        LEFT JOIN events e ON e.event_id = s.event_id
        ORDER BY s.survey_id
    """)
    out = []
    for r in rows:
        email = r["email"]
        identified = r["matched"] == "Y"
        answers = drop_none({
            "Q1": r["q1_satisfaction"], "Q2": r["q2_helpfulness"], "Q3": r["q3_recommend"],
            "Q4": r["q4_helpful_content"], "Q5": r["q5_wanted_topic"],
            "Q6": ADOPTION_LABEL.get(r["q6_adoption"]), "Q7": YES_NO_LABEL.get(r["q7_contact_wish"]),
            "Q8": email,
        })
        out.append(drop_none({
            "responseId": r["survey_id"],
            "eventId": r["event_id"],
            "answers": {k: str(v) for k, v in answers.items()},
            "email": email,
            "customerLinkKey": f"{r['event_id']}:{email}" if email else None,
            "identified": identified,
            "contactFollowUp": r["q7_contact_wish"] == "Y",
            "eventName": r["event_name"],
            "responseDate": r["response_date"],
            "linkedState": "연결 완료" if identified else "연결 확인 필요" if email else "익명 응답",
        }))
    return out


@app.get("/interactions")
def interactions():
    return query("""
        SELECT i.interaction_id AS id, i.event_id AS eventId, e.event_name AS eventName,
               i.name, i.company, i.email,
               i.contact_date AS contactDate, i.method, i.memo, i.result
        FROM interactions i
        LEFT JOIN events e ON e.event_id = i.event_id
        ORDER BY i.interaction_id
    """)


@app.get("/contents")
def contents():
    return query("""
        SELECT content_id AS contentId, published_date AS publishedDate, channel, title, topic, audience, url
        FROM contents ORDER BY content_id
    """)
