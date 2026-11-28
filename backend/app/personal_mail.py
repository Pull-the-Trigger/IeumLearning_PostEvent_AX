"""개인 맞춤 메일 화면용 조회 API (GET /personal-mail).

맞춤 메일 초안은 backend/custom_mail/build_mails.py 가 만든 out/custom_mails.csv 를 그대로 씁니다.
화면은 판단하지 않고 이 값을 보여 줍니다 (요구사항 U04).
  - 받는 사람: 맞춤 메일이 있는 출석자만 (갈래 THANKS_ONLY는 감사 메일만 받으므로 제외, REQ-A05)
  - 제목·본문: 템플릿 + AI 연결 문장 (REQ-A07)
  - 한 통씩 승인 / 묶음 승인: approval 칸 (REQ-A15)
  - 약속 날짜·담당자·추천 글·자동 검사 결과: analysis 로 같이 보냄

먼저 실행 (저장소 루트):
    python backend/custom_mail/build_mails.py --include-drafts
"""
import csv
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.db.conn import ROOT, read_env

router = APIRouter()

SENDER = "이음러닝 마케팅본부장 한서윤"  # REQ-A19
BRANCH_LABEL = {
    "SALES": "영업 담당 상담", "ARTICLE": "발행 글로 답변", "STAFF": "담당자 확인 후 답변",
    "CUSTOM_TOPIC": "관심 주제 글 추천", "THANKS_ONLY": "감사 메일만",
}
ADOPTION_LABEL = {"Y": "예", "REVIEW": "검토 중", "N": "아니오"}
YES_NO_LABEL = {"Y": "예", "N": "아니오"}

# 사전 질문(question_map.json의 match) → 화면 질문 주제 Q01~Q08.
# 토요일 안건 8 '질문 분류 통일'의 짝짓기 초안 — 팀 확인 전.
QUESTION_TOPIC = {
    "현업이 직접 만들 수 있는": "Q01", "반복 보고서": "Q01", "영업 조직에 맞는 실습": "Q01",
    "비개발 직군": "Q02", "교육 시간을 업무 시간": "Q02",
    "사내 자료를 넣어도": "Q03", "사용 규정을 어떻게": "Q03", "코딩 테스트에 AI": "Q03",
    "교육 전후 차이": "Q04", "경영진 보고용 지표": "Q04", "부서별 수준 차이": "Q04",
    "1년 계획": "Q05", "어느 부서부터": "Q05", "예산이 한정": "Q05", "작은 회사는 무엇부터": "Q05",
    "전담 조직": "Q06", "인사 평가와 연결": "Q06",
    "경력직 평가 문항": "Q07", "전 직원 대상으로 진단": "Q07",
}


def _path(env_name, default):
    value = read_env(env_name)
    if not value:
        return default
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def question_topic(question):
    if not question:
        return None
    return next((topic for match, topic in QUESTION_TOPIC.items() if match in question), "Q08")


def _survey_answers(survey):
    if not survey:
        return None
    answers = {"q4": survey.get("q4_helpful_content"), "q5": survey.get("q5_wanted_topic"),
               "q6": ADOPTION_LABEL.get(survey.get("q6_adoption")), "q7": YES_NO_LABEL.get(survey.get("q7_contact_wish"))}
    return {k: v for k, v in answers.items() if v}


def build_personal_mail():
    mails_path = _path("CUSTOM_MAILS_PATH", ROOT / "out" / "custom_mails.csv")
    if not mails_path.exists():
        raise HTTPException(503, "맞춤 메일 결과가 없습니다. python backend/custom_mail/build_mails.py --include-drafts 를 먼저 실행해 주세요.")
    mails = _read_csv(mails_path)
    events_csv = {r["event_id"]: r for r in _read_csv(ROOT / "data" / "processed" / "events.csv")}
    profiles_path = ROOT / "data" / "processed" / "profiles.json"
    profiles = {p["email"].strip().lower(): p for p in json.loads(profiles_path.read_text(encoding="utf-8"))} if profiles_path.exists() else {}

    events, drafts, goals = {}, {}, {}
    for m in mails:
        eid, email = m["event_id"], m["email"].strip().lower()
        ev = events_csv.get(eid, {})
        if eid not in events:
            surveys = [s for p in profiles.values() for s in p.get("surveys", []) if s.get("event_id") == eid]
            identified = sum(1 for s in surveys if s.get("matched") == "Y")
            events[eid] = {
                "id": eid, "name": m["event_name"], "eventDate": ev.get("event_date", ""),
                "appliedCount": int(ev.get("applied_count") or 0), "attendedCount": int(ev.get("attended_count") or 0),
                "surveyCount": int(ev.get("survey_count") or 0), "surveyIdentifiedCount": identified,
                "surveyAnonymousCount": max(0, int(ev.get("survey_count") or 0) - identified),
                "materialsUrl": "", "surveyUrl": "", "status": "review", "recipients": [],
                "addedRecipientIds": [], "excludedRecipientIds": [], "includeMaterials": False, "includeSurvey": False,
                "senderName": SENDER, "subject": "", "greeting": "", "materialsParagraph": "", "surveyParagraph": "",
                "scheduledDate": "", "scheduledTime": "", "approved": False, "history": [],
            }
            goals[eid] = {"businessDays": 3, "targetDate": m["send_by"]}  # 행사 다음 날부터 영업일 3일 (REQ-A16)

        p = profiles.get(email, {})
        survey = next((s for s in p.get("surveys", []) if s.get("event_id") == eid), None)
        memo = next((i.get("memo") for i in p.get("interactions", []) if i.get("event_id") == eid), None)
        person = {
            "id": email, "name": m["name"], "company": m["company"], "title": m["title"], "email": email,
            "attended": True, "consent": m["consent"] if m["consent"] in ("Y", "N") else "UNKNOWN",
            "attendanceCount": int(p.get("attended_count") or 1), "surveyResponded": survey is not None,
        }
        if m["pre_question"]:
            person["preQuestion"] = m["pre_question"]
        if memo:
            person["interactionMemo"] = memo
        answers = _survey_answers(survey)
        if answers:
            person["surveyAnswers"] = answers
        events[eid]["recipients"].append(person)

        topic = question_topic(m["pre_question"])
        drafts[f"{eid}:{email}"] = {
            "eventId": eid, "customerId": email,
            "status": "review", "reviewed": False,  # AI 초안이 있으므로 '검토 대기'에서 시작 (사람이 검토 완료를 눌러야 함)
            "requiredReview": m["approval"] == "한 통씩 승인",
            "excluded": False,
            "questionTypes": [topic] if topic else [], "questions": [m["pre_question"]] if m["pre_question"] else [],
            "sender": SENDER, "subject": m["subject"], "body": m["body"], "attachments": [], "history": [],
            "followUps": {"reply": m["branch"] == "STAFF", "material": False, "sales": m["branch"] == "SALES"},
            "analysis": {
                "branch": m["branch"], "branchLabel": BRANCH_LABEL.get(m["branch"], m["branch"]),
                "approval": m["approval"], "sendBy": m["send_by"],
                "promiseDue": m["promise_due"] or None, "assignedStaff": m["assigned_staff"] or None,
                "contactMode": m["contact_mode"] or None,
                "article": m["article"] or None, "articleReason": m["article_reason"] or None,
                "answer": m["answer"] or None, "surveyTopic": m["survey_topic"] or None,
                "industry": p.get("industry_major") or None,
                "sentenceSource": m["sentence_source"], "lint": m["lint"] or None, "note": m["note"] or None,
            },
        }
    return {"events": list(events.values()), "drafts": drafts, "goals": goals}


@router.get("/personal-mail")
def personal_mail():
    return build_personal_mail()
