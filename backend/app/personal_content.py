"""개인 맞춤 콘텐츠 화면용 조회 API (GET /personal-content).

발행 글(contents.csv)마다 '이 글을 누구에게 보내면 좋을지'를 실제 기록으로 고른다.
화면의 추천 유형 R01~R06(팀원 설계)과 표시할 근거 칸은 그대로 쓰고, 판단은 여기서 한다 (요구사항 U04).

유형별 기준 (11/28 팀 논의)
  R01 질문 연계형  사전 질문이 이 글과 같은 주제 (질문 → question_map.json의 연결 글 → 그 글의 주제)   → 마케팅 발송
  R04 교류 이력형  후속 연락 기록이 있고, 그 사람의 질문·관심 주제가 이 글 주제                       → 마케팅 발송
  R02 관심 주제형  설문 Q5 '듣고 싶은 주제'가 이 글 주제                                              → 마케팅 발송
  R03 도입 검토형  설문 Q6 도입 검토 '예'·'검토 중' + 글 주제가 도입 우선순위·전환 로드맵
                   → 이 사람들은 영업 전달 대상(S01)이라 마케팅이 보내지 않고 '영업 담당 전달'로 표시 (B06)
  R05 직무 연계형  직함으로 본 직무 = 글의 대상 독자. 이것만으로는 보내지 않고(B05 '짐작 금지'),
                   한 사람이 여러 글에 걸릴 때 어느 글을 줄지 고르는 데만 쓴다
  R06 행사 연계형  행사에 신청했지만 오지 않은 사람에게, 행사 '이후' 발행된 그 행사 후기 글
공통: 수신 동의자만 (B01) / 맞춤 메일에서 이미 보낸 글은 빼기 / 한 사람에게 1편만 (B04 '2주마다 1편')
     → 1편 고르는 순서: 유형(R01 > R04 > R02 > R06) → 글 대상 독자가 직무와 맞는 글 → 최근 발행 글
"""
import csv
import json
import re

from fastapi import APIRouter

from backend.db.conn import ROOT

router = APIRouter()
PROCESSED = ROOT / "data" / "processed"

HANDOFF_REASON = "영업 담당 전달 — 도입 검토 고객은 영업 담당이 연락하므로 상담 때 함께 보낼 글로 넘김"
ADOPTION_TOPICS = {"AI 도입 우선순위", "AI 전환 로드맵"}
ADOPTION_LABEL = {"Y": "예", "REVIEW": "검토 중", "N": "아니오"}
YES_NO_LABEL = {"Y": "예", "N": "아니오"}
AUDIENCE_ROLE = {"경영진": "경영진", "HR 담당자": "HR", "교육 담당자": "교육", "DX 담당자": "DX·AX",
                 "IT 담당자": "IT", "개발팀장": "개발", "현업 팀장": "현업"}
REVIEW_EVENT = {"HR": "E02", "CEO": "E01", "부산": "E04", "빌더톤": "E03"}  # 행사 후기 글 제목 → 행사


def _csv(name):
    with open(PROCESSED / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def role_of(title):
    t = title or ""
    for role, pattern in [("경영진", r"대표|CEO|임원|전무|상무|부사장|사장|본부장|실장"), ("HR", r"인사|HR"),
                          ("교육", r"교육|러닝|인재"), ("DX·AX", r"DX|AX|디지털"), ("IT", r"IT|정보|전산"),
                          ("개발", r"개발|CTO"), ("현업", r"팀장|부장|과장|매니저|책임")]:
        if re.search(pattern, t):
            return role
    return "기타(미확인)"


def build_personal_content():
    contents = _csv("contents.csv")
    arts = {a["content_id"]: a for a in contents}
    events = {e["event_id"]: e for e in _csv("events.csv")}
    rules = json.loads((ROOT / "backend" / "pre_question" / "question_map.json").read_text(encoding="utf-8"))["rules"]
    profiles = json.loads((PROCESSED / "profiles.json").read_text(encoding="utf-8"))
    sent = {}  # 맞춤 메일에서 이미 보낸 글: email → {content_id}
    mails_path = ROOT / "out" / "custom_mails.csv"
    if mails_path.exists():
        with open(mails_path, encoding="utf-8-sig", newline="") as f:
            for m in csv.DictReader(f):
                if m.get("article"):
                    sent.setdefault(m["email"].strip().lower(), set()).add(m["article"].split(" ")[0])

    def question_rule(q):
        return next((r for r in rules if r["match"] in q and r.get("article") in arts), None)

    def ev(eid, *keys):
        e = events.get(eid, {})
        names = {"name": ("관련 행사", e.get("event_name")), "date": ("개최일", e.get("event_date")), "type": ("행사 유형", e.get("event_type"))}
        return [{"label": names[k][0], "value": names[k][1] or "확인 필요"} for k in keys]

    people = []
    for p in profiles:
        if not p.get("email") or not p.get("events"):
            continue
        attended = [e for e in p["events"] if e["attended"] == "Y"]
        last = sorted(p["events"], key=lambda e: e["event_date"])[-1]
        questions = []
        for e in attended:
            if e.get("pre_question"):
                rule = question_rule(e["pre_question"])
                questions.append((e["event_id"], e["pre_question"], arts[rule["article"]]["topic"] if rule else None, rule.get("label", "") if rule else ""))
        surveys = p.get("surveys", [])
        customer = {
            "id": p["email"], "name": p["name"], "company": p["company"], "title": p.get("title") or "", "email": p["email"],
            "attended": bool(attended), "consent": p["consent"] if p["consent"] in ("Y", "N") else "UNKNOWN",
            "attendanceCount": len(attended), "surveyResponded": bool(surveys),
        }
        if questions:
            customer["preQuestion"] = questions[-1][1]
        if p.get("interactions"):
            customer["interactionMemo"] = p["interactions"][-1].get("memo")
        if surveys:
            s0 = surveys[-1]
            ans = {"q4": s0.get("q4_helpful_content"), "q5": s0.get("q5_wanted_topic"),
                   "q6": ADOPTION_LABEL.get(s0.get("q6_adoption")), "q7": YES_NO_LABEL.get(s0.get("q7_contact_wish"))}
            customer["surveyAnswers"] = {k: v for k, v in ans.items() if v}
        people.append({"p": p, "customer": customer, "questions": questions, "last": last, "role": role_of(p.get("title"))})

    publications, candidates = [], []
    for a in contents:
        publications.append({"id": a["content_id"], "publishedAt": a["published_date"], "channel": a["channel"], "title": a["title"],
                             "topic": a["topic"], "audience": a["audience"], "link": a["url"]})
        topic = a["topic"]
        review_eid = next((eid for k, eid in REVIEW_EVENT.items() if k in a["title"]), None) if topic == "행사 후기" else None
        review_after_event = bool(review_eid) and a["published_date"] > events.get(review_eid, {}).get("event_date", "9999")
        for x in people:
            p = x["p"]
            q_hit = next((q for q in x["questions"] if q[2] == topic), None)
            q5 = next((s for s in p.get("surveys", []) if s.get("q5_wanted_topic") == topic), None)
            q6 = next((s for s in p.get("surveys", []) if s.get("q6_adoption") in ("Y", "REVIEW")), None)
            inter = p.get("interactions", [])
            no_show = review_after_event and any(e["event_id"] == review_eid and e["attended"] != "Y" for e in p["events"])
            if q_hit:
                typ, eid = "R01", q_hit[0]
                sections = ev(eid, "name", "date") + [{"label": "질문 유형", "value": q_hit[3] or "질문 사전에 없음"}, {"label": "질문 원문", "value": q_hit[1]}]
                values, sources = [q_hit[1]], ["참가자 명단 · 사전 질문"]
                reason = f"{events[eid]['event_name']} 사전 질문이 이 글과 같은 주제({topic})입니다."
            elif inter and (topic in [q[2] for q in x["questions"]] or any(s.get("q5_wanted_topic") == topic for s in p.get("surveys", []))):
                typ, i = "R04", inter[-1]
                eid = i["event_id"]
                sections = ev(eid, "name") + [{"label": "연락일", "value": i.get("contact_date") or "확인 필요"},
                                              {"label": "연락 방법", "value": i.get("method") or "확인 필요"},
                                              {"label": "문의 및 요청 내용", "value": i.get("memo") or "기록 없음"},
                                              {"label": "처리 결과", "value": i.get("result") or "기록 없음"}]
                values, sources = [i.get("memo") or ""], ["후속 연락 기록"]
                reason = f"후속 연락 기록이 있고, 남긴 질문·관심 주제가 이 글 주제({topic})입니다."
            elif q5:
                typ, eid = "R02", q5["event_id"]
                sections = ev(eid, "name", "date") + [{"label": "설문 응답일", "value": q5.get("response_date") or "확인 필요"}, {"label": "관심 주제 원문", "value": topic}]
                values, sources = [topic], ["만족도 설문 · Q5"]
                reason = f"설문에서 듣고 싶은 주제로 '{topic}'을(를) 적었습니다."
            elif q6 and topic in ADOPTION_TOPICS:
                typ, eid = "R03", q6["event_id"]
                label = ADOPTION_LABEL[q6["q6_adoption"]]
                sections = ev(eid, "name") + [{"label": "설문 응답일", "value": q6.get("response_date") or "확인 필요"}, {"label": "도입 검토 응답 내용", "value": label}]
                values, sources = [label], ["만족도 설문 · Q6"]
                reason = f"설문에서 AI 교육·진단 도입 검토를 '{label}'(으)로 답했습니다. 영업 담당이 상담할 때 함께 보낼 글로 넘깁니다."
            elif no_show:
                typ, eid = "R06", review_eid
                sections = ev(eid, "name", "date", "type") + [{"label": "참석 여부", "value": "신청 후 불참"}]
                values, sources = [events[eid]["event_name"]], ["참가자 명단 · 신청·참석"]
                reason = f"{events[eid]['event_name']}에 신청했고(불참), 행사 후 발행된 후기 글입니다. 메일에는 불참 얘기 없이 신청 사실만 씁니다."
            elif x["role"] == AUDIENCE_ROLE.get(a["audience"]) and x["customer"]["attended"]:
                typ, eid = "R05", x["last"]["event_id"]
                sections = [{"label": "실제 직함", "value": x["customer"]["title"] or "미확인"},
                            {"label": "분류된 직무", "value": x["role"]}, {"label": "콘텐츠 대상 독자", "value": a["audience"]}]
                values, sources = [x["customer"]["title"]], ["참가자 명단 · 직함"]
                reason = f"직함으로 본 직무({x['role']})가 글의 대상 독자({a['audience']})와 같습니다."
            else:
                continue
            e = events.get(eid, {})
            c = x["customer"]
            row = {"id": f"{a['content_id']}:{c['id']}", "publicationId": a["content_id"], "customer": c, "type": typ,
                   "supportingEvidence": values, "evidenceSource": sources, "evidenceSections": sections, "reason": reason,
                   "roleClassification": x["role"], "relatedEvent": {"name": e.get("event_name", ""), "eventDate": e.get("event_date", "")}}
            # 제외 이유 (먼저 걸리는 것)
            if c["consent"] != "Y":
                row["excludedReason"] = "마케팅 수신 미동의" if c["consent"] == "N" else "마케팅 수신 동의 여부 미확인"
            elif a["content_id"] in sent.get(c["id"], set()):
                row["excludedReason"] = "맞춤 메일에서 이미 보낸 글"
            elif typ == "R03":
                row["excludedReason"] = HANDOFF_REASON
            elif typ == "R05":
                row["excludedReason"] = "직무만으로는 보내지 않음 (질문·설문·교류·불참 기록 없음)"
            candidates.append((row, a, x["role"]))

    # 한 사람에게 1편만: 유형 → 대상 독자가 직무와 맞는 글 → 최근 발행 순으로 고르고, 나머지는 제외 목록에 남긴다
    rank = {"R01": 0, "R04": 1, "R02": 2, "R06": 3}
    best = {}
    for row, a, role in candidates:
        if "excludedReason" in row:
            continue
        key = (rank[row["type"]], AUDIENCE_ROLE.get(a["audience"]) != role, "".join(chr(0x10FFFF - ord(ch)) for ch in a["published_date"]), a["content_id"])
        cid = row["customer"]["id"]
        if cid not in best or key < best[cid][0]:
            best[cid] = (key, row["id"], a)
    recommendations = {a["content_id"]: [] for a in contents}
    for row, a, role in candidates:
        cid = row["customer"]["id"]
        if "excludedReason" not in row and best[cid][1] != row["id"]:
            row["excludedReason"] = f"이번 회차는 다른 글로 추천: 「{best[cid][2]['title']}」 (1인 1편)"
        elif "excludedReason" not in row and row["type"] != "R06" and AUDIENCE_ROLE.get(a["audience"]) == role:
            row["reason"] += f" 같은 주제 글 중 대상 독자({a['audience']})가 직무와 맞는 글을 골랐습니다."
        recommendations[a["content_id"]].append(row)
    return {"publications": publications, "recommendations": recommendations}


@router.get("/personal-content")
def personal_content():
    return build_personal_content()
