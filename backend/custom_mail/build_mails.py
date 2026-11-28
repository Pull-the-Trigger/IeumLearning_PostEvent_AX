"""출석자별 맞춤 메일 초안 + 영업 전달 패키지.

  python backend/custom_mail/build_mails.py              # 메일 보내는 날까지 발행된 글만 사용 (실제 상황)
  python backend/custom_mail/build_mails.py --as-of today # 지금 있는 글 전부 사용 (다음 행사 시연용)

1. plan_followups로 출석자별 갈래를 정한다 (영업 / 글 안내 / 담당자 / 사실 / 설문 주제 / 감사 메일만)
2. 글을 고른다 — 사전 질문: question_map.json의 article (검수된 짝)
                   처음 보는 질문: AI가 36편 중 고름, 맞는 글 없으면 '없음'
                   설문 주제: 같은 주제 글 중 직함에 맞는 대상 독자의 글
3. 갈래별 문안 틀에 넣는다 — 문장은 사람이 정한 틀만 쓰고 AI는 문장을 쓰지 않는다 (지어내기 방지)
4. 06 글쓰기 기준 검사 (합니다체, 금지 표현, 느낌표·이모지, 제품명 표기)

출력: out/custom_mails.csv (본부장 검토용 메일 초안), out/sales_handoff.csv (영업 담당자용 근거),
      out/content_gaps.csv (다음에 쓸 글 목록), out/answer_bank_review.csv (답변 재료집 검수표)
모든 메일은 초안이다. 본부장 승인 전에는 발송하지 않는다.
"""
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend" / "pre_question"))
sys.path.insert(0, str(HERE))
from mail_writer import render_mail  # noqa: E402
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "out"

SENDER = "이음러닝 마케팅본부장 한서윤"   # 발신자: 마케팅본부장 명의 (인터뷰 9번)
CONTACT_BUSINESS_DAYS = 3               # 영업 담당자 연락 기한: 메일 발송 후 영업일 3일

AUDIENCE_BY_TITLE = [  # 직함 → 글의 '대상 독자' (위에서부터 먼저 맞는 것)
    (("대표", "CEO", "전무", "부사장", "상무", "본부장", "실장", "이사", "공장장"), "경영진"),
    (("CTO", "개발"), "개발팀장"),
    (("인사", "HR", "조직문화", "채용"), "HR 담당자"),
    (("교육", "HRD"), "교육 담당자"),
    (("DX", "데이터"), "DX 담당자"),
    (("IT", "정보", "보안"), "IT 담당자"),
]

# 06 글쓰기 기준 검사
BANNED = ["혁신적", "획기적", "압도적", "지금 바로", "놓치지 마세요", "마지막 기회",
          "이음진단", "진단 툴", "부트캠프", "이러닝"]
HAEYO = re.compile(r"(해요|에요|예요|죠|드려요|어요|아요)[.!?\s]")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def read(name):
    with open(PROCESSED / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def add_business_days(d, n):
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def audience_for(title):
    for keys, aud in AUDIENCE_BY_TITLE:
        if any(k in title for k in keys):
            return aud
    return "현업 팀장"


def lint(text):
    warns = [f"금지 표현 '{w}'" for w in BANNED if w in text]
    if HAEYO.search(text):
        warns.append("합니다체 아님")
    if "!!" in text or "！！" in text:
        warns.append("느낌표 두 개 이상")
    if EMOJI.search(text):
        warns.append("이모지")
    return warns


class ArticlePicker:
    def __init__(self):
        self.arts = {a["content_id"]: a for a in read("contents.csv")}
        rules = json.loads((ROOT / "backend" / "pre_question" / "question_map.json").read_text(encoding="utf-8"))["rules"]
        self.rules = rules
        self.cache = {}

    def for_question(self, q, as_of, title=""):
        """as_of(메일 보내는 날) 이전에 발행된 글만 쓴다."""
        for r in self.rules:
            if r["match"] in q and r.get("article"):
                a = self.arts[r["article"]]
                if a["published_date"] <= as_of.isoformat():
                    return a, "질문 사전에 연결된 글"
                # 같은 주제의 다른 글로 바꾸지 않는다: 질문과 직접 맞는 글만 보낸다 (인터뷰·06 기준)
                return None, f"맞는 글({a['content_id']})이 {a['published_date']} 발행이라 메일 시점엔 없음 → 관심 분야로 기록"
        key = (q, as_of)
        if key in self.cache:
            return self.cache[key]
        res = (None, "맞는 글 없음 (AI 미사용)")
        if os.getenv("OPENAI_API_KEY"):
            res = self._llm(q, as_of)
        self.cache[key] = res
        return res

    def label(self, q):
        for r in self.rules:
            if r["match"] in q:
                return r.get("label", "")
        return ""

    def for_topic(self, topic, title, as_of, used=()):
        aud = audience_for(title)
        cands = [a for a in self.arts.values() if a["topic"] == topic and a["topic"] != "행사 후기"
                 and a["published_date"] <= as_of.isoformat()]
        cands.sort(key=lambda a: (a["audience"] != aud, a["content_id"] in used, a["content_id"]))
        if not cands:
            return None, "이 주제의 글 없음 → 관심 분야로 기록"
        return cands[0], f"설문 주제 '{topic}' + 대상 독자 '{aud}'"

    def _llm(self, q, as_of):
        from openai import OpenAI
        lst = "\n".join(f"{a['content_id']} | {a['title']} | {a['topic']} | {a['audience']}"
                        for a in self.arts.values()
                        if a["topic"] != "행사 후기" and a["published_date"] <= as_of.isoformat())
        schema = {"type": "object", "additionalProperties": False, "required": ["content_id", "reason"],
                  "properties": {"content_id": {"type": "string"}, "reason": {"type": "string"}}}
        resp = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            messages=[{"role": "system", "content":
                       "행사 참가자의 질문과 직접 관련된 글 하나를 목록에서 고른다. 제목·주제·대상 독자만 보고 판단한다. "
                       "질문과 직접 관련된 글이 없으면 content_id에 NONE을 쓴다. 억지로 고르지 않는다.\n" + lst},
                      {"role": "user", "content": q}],
            response_format={"type": "json_schema", "json_schema": {"name": "pick", "strict": True, "schema": schema}})
        out = json.loads(resp.choices[0].message.content)
        a = self.arts.get(out["content_id"])
        return (a, "AI: " + out["reason"]) if a else (None, "맞는 글 없음 (AI 판단) → 관심 분야로 기록")


def load_staff():
    """담당자 목록(가상, backend/custom_mail/staff_directory.csv). 실제 운영 땐 이 표만 바꾸면 된다."""
    with open(HERE / "staff_directory.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def assign_staff(staff, role, industry_major, company):
    """산업군 대분류 코드가 맞는 담당자 → 없으면 '*' 담당자. 같은 회사는 항상 같은 사람."""
    import zlib
    pool = [s for s in staff if s["role"] == role]
    code = (industry_major or "").split(" ")[0]
    cand = [s for s in pool if code and code in s["industries"].split("|")] or [s for s in pool if s["industries"] == "*"] or pool
    return cand[zlib.crc32(company.encode("utf-8")) % len(cand)]


def josa_iga(word):
    ch = word.strip()[-1]
    return "이" if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else "가"


def load_answers(include_drafts):
    """답변 재료집: 근거(basis)가 있는 것만. 그중 approved만 (include_drafts면 draft도 미리 보기).
    근거가 없는 답변은 승인 여부와 상관없이 절대 메일에 넣지 않는다."""
    data = json.loads((HERE / "answer_bank.json").read_text(encoding="utf-8"))["answers"]
    ok = ("approved", "draft") if include_drafts else ("approved",)
    usable, blocked = {}, []
    for k, v in data.items():
        if not v.get("text"):
            continue
        if not v.get("basis"):
            blocked.append(k)
            continue
        if v.get("status") in ok:
            usable[k] = v
    if blocked:
        print(f"근거가 없어 메일에 넣지 않는 답변 {len(blocked)}개: {', '.join(blocked)}")
    return usable


def fact_check(r, subject, body, rep, due, contact_mode, art, survey_line):
    """메일이 '그 사람이 실제로 한 일'과 '우리가 정한 약속'만 말하는지 확인 (사람이 읽기 전에 자동으로 거른다)."""
    w = []
    surveyed = bool(survey_line) or "설문" in r.get("sales_triggers", "") or bool(r.get("known_topic"))
    if "남겨 주신" in subject and not r["pre_question"] and not r.get("survey_topic"):
        w.append("사실: 제목에 '남겨 주신'인데 남긴 질문·설문이 없음")
    if "신청하시며" in body and not r["pre_question"]:
        w.append("사실: 신청 질문을 언급했는데 질문이 없음")
    if "설문에서" in body and not surveyed:
        w.append("사실: 설문을 언급했는데 설문 기록이 없음")
    if r["consent"] != "Y":
        if r["branch"] == "SALES" and contact_mode == "first" and "요청해 주셔서" not in body:
            w.append("동의: 수신 미동의자에게 먼저 연락하는데 본인 요청이라는 이유가 없음")
        if r["branch"] == "SALES" and contact_mode == "on_reply" and re.search(r"\d+월 \d+일까지 연락", body):
            w.append("동의: 회신 오면 연락할 사람에게 날짜를 약속함")
        if re.search(r"할인|무료|프로모션|특가|얼리버드", subject + body):
            w.append("동의: 수신 미동의자에게 홍보 문구")
    if rep and r["branch"] in ("SALES", "STAFF") and rep["name"] not in body:
        w.append("약속: 배정 담당자 이름이 본문에 없음")
    if r["branch"] in ("SALES", "STAFF") and contact_mode == "first" and f"{due.month}월 {due.day}일" not in body:
        w.append("약속: 연락 날짜가 본문과 다름")
    if art and art["title"] not in body:
        w.append("글: 고른 글 제목이 본문에 없음")
    if body.count("감사합니다") > 1:
        w.append("문장: 감사 인사 중복")
    if r.get("known_topic") and "회신으로 한 줄" in body:
        w.append("되묻기: 설문에 관심 주제를 남긴 사람에게 다시 회신을 요청함")
    return w


def trigger_sentence(triggers):
    """질문 없는 영업 메일: 왜 연락하는지 그 사람이 남긴 사실로 한 문장."""
    if "설문 연락 희망" in triggers:
        return "설문에서 담당자 연락을 요청해 주셔서 연락드립니다."
    if "설문 도입 검토(검토 중)" in triggers:
        return "설문에서 AI 교육 도입을 검토 중이라고 답해 주셔서 연락드립니다."
    if "설문 도입 검토" in triggers:
        return "설문에서 AI 교육 도입을 검토하고 계시다고 답해 주셔서 연락드립니다."
    if "현장·후속 기록" in triggers:
        return "행사장에서 나눈 이야기와 관련해 이어서 연락드립니다."
    return ""


def main(as_of_mode="send", include_drafts=False):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    import plan_followups
    rows = plan_followups.main(str(OUT / "followup_plan"))
    events = {e["event_id"]: e for e in read("events.csv")}
    parts = [p for p in read("participation.csv") if p["attended"] == "Y" and p.get("is_test") != "True"]
    inter = read("interactions.csv")
    surveys = {(s["event_id"], s["email"].strip().lower()): s for s in read("surveys.csv") if s.get("email")}
    picker = ArticlePicker()
    staff = load_staff()
    answers = load_answers(include_drafts)
    bank_all = json.loads((HERE / "answer_bank.json").read_text(encoding="utf-8"))["answers"]
    # 산업군(내부용, 팀원 data 브랜치 11/25): 영업 전달 패키지에만 쓰고 메일 본문에는 쓰지 않는다
    industry = {}
    pj = PROCESSED / "profiles.json"
    if pj.exists():
        for p in json.loads(pj.read_text(encoding="utf-8")):
            industry[p["email"].strip().lower()] = (p.get("industry_major") or "", p.get("industry_mid") or "")

    def mode_of(r):  # 수신 미동의 영업 건은 회신 오면 연락 (설문 연락 요청은 예외)
        return ("on_reply" if r["branch"] == "SALES" and r["consent"] != "Y"
                and "설문 연락 희망" not in r["sales_triggers"] else "first")

    # 여러 행사에 온 사람: 앞 행사에서 이미 영업 담당자를 안내했으면, 다음 행사 메일은 '이어서'로 쓴다
    prior_sales = {}   # (event_id, email) -> 앞서 담당자를 안내한 행사 이름
    seen = {}
    for r in sorted(rows, key=lambda x: (events[x["event_id"]]["event_date"], x["event_id"])):
        if r["branch"] == "SALES" and mode_of(r) == "first":
            if r["email"] in seen:
                prior_sales[(r["event_id"], r["email"])] = seen[r["email"]]
            else:
                seen[r["email"]] = r["event_name"]

    from collections import Counter as _C
    same_co = _C((r["event_id"], r["company"]) for r in rows if r["branch"] != "THANKS_ONLY")
    mails, handoff = [], []
    for r in rows:
        if r["branch"] == "THANKS_ONLY":
            continue
        ev_date = date.fromisoformat(events[r["event_id"]]["event_date"])
        prev = sorted((events[p["event_id"]]["event_date"], events[p["event_id"]]["event_name"])
                      for p in parts if p["email"].strip().lower() == r["email"]
                      and events[p["event_id"]]["event_date"] < events[r["event_id"]]["event_date"])
        prev_event = prev[-1][1] if prev else ""
        send_by = date.fromisoformat(r["send_by"]) if r["send_by"] else add_business_days(ev_date, 3)
        art, art_why = (None, "")
        if r["pre_question"]:
            art, art_why = picker.for_question(r["pre_question"], as_of(send_by, as_of_mode), r["title"])
        elif r["branch"] == "CUSTOM_TOPIC":
            art, art_why = picker.for_topic(r["survey_topic"], r["title"], as_of(send_by, as_of_mode))
        note = ""
        if r["branch"] == "ARTICLE" and not art:
            if answers.get(picker.label(r["pre_question"])):
                note = "맞는 글은 없지만 근거 있는 답변이 있어 답변만 보냄"
            else:
                r = {**r, "branch": "STAFF"}
                note = "맞는 글도 답변도 없어 담당자로 전환"
        if r["branch"] == "CUSTOM_TOPIC" and not art:
            note = "주제에 맞는 글 없음 → 맞춤 메일 생략, 관심 분야 기록"
            mails.append({**_base(r), "subject": "", "body": "", "sentence_source": "", "answer": "", "assigned_staff": "", "contact_mode": "", "promise_due": "", "article": "",
                          "article_reason": art_why, "note": note, "lint": ""})
            continue
        due = add_business_days(send_by, CONTACT_BUSINESS_DAYS)
        ind_major = industry.get(r["email"], ("", ""))[0]
        rep = None
        if r["branch"] in ("SALES", "STAFF"):
            rep = assign_staff(staff, r["branch"], ind_major if r["branch"] == "SALES" else "", r["company"])
        sv = surveys.get((r["event_id"], r["email"]), {})
        helpful = (sv.get("q4_helpful_content") or "").strip()
        survey_line = f"설문에서 ‘{helpful}’{josa_iga(helpful)} 도움이 되었다고 남겨 주셔서 감사합니다." if helpful else ""
        known_topic = (sv.get("q5_wanted_topic") or "").strip()  # 이미 알려준 관심사 → 다시 묻지 않음
        label = picker.label(r["pre_question"])
        ans = answers.get(label, {}) if r["pre_question"] and r["branch"] in ("SALES", "ARTICLE") else {}
        staff_why = "sensitive" if bank_all.get(label, {}).get("status") == "not_for_first_mail" else "no_basis"
        # 수신 미동의자의 영업 건: 먼저 연락하지 않고 회신 오면 연락 (설문에서 직접 연락을 요청한 경우는 예외)
        contact_mode = mode_of(r)
        continued_from = prior_sales.get((r["event_id"], r["email"]), "") if r["branch"] == "SALES" else ""
        subject, body, src, co_note = render_mail(r, art, prev_event, due, label,
                                                  same_co[(r["event_id"], r["company"])], rep, survey_line,
                                                  ans.get("text", ""), trigger_sentence(r["sales_triggers"]), staff_why, contact_mode,
                                                  continued_from, known_topic)
        if ans.get("status") == "draft":
            lvl = {"strong": "근거 충분", "partial": "근거 일부 — 보강 필요"}.get(ans.get("basis_level"), "")
            co_note = "; ".join(x for x in [co_note, f"검수 전 답변 포함({lvl}) — 승인 필요"] if x)
        warns = lint(subject + "\n" + body) + fact_check({**r, "known_topic": known_topic}, subject, body, rep, due, contact_mode, art, survey_line)
        mails.append({**_base(r), "subject": subject, "body": body, "sentence_source": src,
                      "answer": ans.get("status", ""),
                      "assigned_staff": f"{rep['name']} {rep['position']} ({rep['team']})" if rep else "",
                      "contact_mode": ({"on_reply": "회신 오면 연락 (수신 미동의)", "first": "먼저 연락"}[contact_mode]
                                       + (f" — 이어서 (앞서 {continued_from}에서 담당자 안내)" if continued_from else "")) if r["branch"] == "SALES" else "",
                      "promise_due": due.isoformat() if r["branch"] in ("SALES", "STAFF") and contact_mode == "first" else "",
                      "article": f"{art['content_id']} {art['title']}" if art else "",
                      "article_reason": art_why, "note": "; ".join(x for x in [note, co_note] if x),
                      "lint": "; ".join(warns)})
        if r["branch"] == "SALES":
            k = (r["event_id"], r["email"])
            s = surveys.get(k, {})
            recs = [f"{i['contact_date']} {i['method']}: {i['memo']} → {i['result']}" for i in inter
                    if i.get("email", "").strip().lower() == r["email"] and i["event_id"] == r["event_id"]]
            handoff.append({
                "event": r["event_name"], "email": r["email"], "name": r["name"], "company": r["company"],
                "industry": " / ".join(x for x in industry.get(r["email"], ("", "")) if x) or "미분류",
                "title": r["title"], "pre_question": r["pre_question"], "sales_triggers": r["sales_triggers"],
                "survey": (f"만족 {s.get('q1_satisfaction')} / 도움 {s.get('q2_helpfulness')} / 추천 {s.get('q3_recommend')} / "
                           f"도움된 내용 '{s.get('q4_helpful_content', '')}' / 듣고 싶은 주제 '{s.get('q5_wanted_topic', '')}' / "
                           f"도입 {s.get('q6_adoption')} / 연락 희망 {s.get('q7_contact_wish')}") if s else "설문 없음",
                "past_contacts": " | ".join(recs) or "없음",
                "previous_event": prev_event,
                "sent_article": f"{art['content_id']} {art['title']}" if art else "",
                "contact_mode": "회신 오면 연락 (수신 미동의 — 먼저 연락하지 말 것)" if contact_mode == "on_reply" else "먼저 연락",
                "sales_status": f"이미 진행 중 — {continued_from}에서 담당자 안내함, 새 질문 추가" if continued_from else "신규",
                "contact_due": add_business_days(send_by, CONTACT_BUSINESS_DAYS).isoformat() if contact_mode == "first" else "",
                "assigned_staff": f"{rep['name']} {rep['position']} ({rep['team']})" if rep else "",
                "staff_email": rep["email"] if rep else "",
            })

    OUT.mkdir(exist_ok=True)
    for name, data in [("custom_mails.csv", mails), ("sales_handoff.csv", handoff)]:
        with open(OUT / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    # 다음에 쓸 글 목록: 질문은 있었는데 메일 시점에 맞는 글이 없었던 것 (인터뷰: 맞는 글 없으면 관심 분야 기록)
    gaps = {}
    for m in mails:
        q = m["pre_question"] or ""
        if not m["body"] and m["branch"] == "CUSTOM_TOPIC":
            key = "설문 주제: " + m["survey_topic"]
        elif q and not m["article"]:
            key = picker.label(q) or q
        else:
            continue
        g = gaps.setdefault(key, {"topic": key, "people": 0, "executives": 0, "events": set(), "sample_question": q,
                                  "matched_article_later": "", "earliest_event": "9999"})
        g["people"] += 1
        g["executives"] += any(t in m["title"] for t in ("대표", "전무", "부사장", "상무", "본부장", "실장", "이사"))
        g["events"].add(m["event_id"])
        g["earliest_event"] = min(g["earliest_event"], events[m["event_id"]]["event_date"])
        why = m["article_reason"]
        if "발행이라" in why:
            g["matched_article_later"] = why.split(" → ")[0]
    gap_rows = []
    for g in sorted(gaps.values(), key=lambda x: -x["people"]):
        gap_rows.append({"topic": g["topic"], "people": g["people"], "executives": g["executives"],
                         "events": ",".join(sorted(g["events"])), "first_asked": g["earliest_event"],
                         "sample_question": g["sample_question"],
                         "status": ("글은 있지만 행사 뒤에 발행됨 — " + g["matched_article_later"]) if g["matched_article_later"] else "새로 써야 할 글",
                         "suggestion": "다음 비슷한 행사 전에 발행하면 맞춤 메일에 바로 넣을 수 있음"})
    if gap_rows:
        with open(OUT / "content_gaps.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(gap_rows[0].keys()))
            w.writeheader()
            w.writerows(gap_rows)

    # 답변집 후보: 질문 사전에 없던(처음 보는) 질문을 모아 몇 번 나왔는지 센다.
    # 2번 이상(여러 사람·여러 행사) 나온 질문 → 답변집 후보. 1번뿐인 질문 → 담당자가 개별 답변으로 끝.
    unseen = {}
    for r in rows:
        if r.get("question_source") in ("llm", "default") and r["pre_question"]:
            key = " ".join(r["pre_question"].split())
            u = unseen.setdefault(key, {"question": key, "count": 0, "events": set(), "branch": r["branch"],
                                        "reason": r.get("question_reason", "")})
            u["count"] += 1
            u["events"].add(r["event_id"])
    with open(OUT / "answer_bank_candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["question", "count", "events", "branch", "ai_reason", "next_step"])
        for u in sorted(unseen.values(), key=lambda x: (-x["count"], x["question"])):
            w.writerow([u["question"], u["count"], ",".join(sorted(u["events"])), u["branch"], u["reason"],
                        "답변집 후보 — 담당자가 답 쓰고 근거 달기" if u["count"] >= 2 else "담당자 개별 답변으로 끝"])

    # 답변 재료집 검수표: 승인하는 사람이 답변과 근거를 한 줄씩 확인
    bank = json.loads((HERE / "answer_bank.json").read_text(encoding="utf-8"))["answers"]
    with open(OUT / "answer_bank_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["topic", "status", "basis_level", "answer", "basis_title", "basis_url", "basis_supports", "note"])
        for k, v in bank.items():
            for b in (v.get("basis") or [{}]):
                w.writerow([k, v.get("status"), v.get("basis_level"), v.get("text"), b.get("title", ""),
                            b.get("url", ""), b.get("supports", ""), v.get("note", "")])

    from collections import Counter
    print("문장 출처:", dict(Counter(m["sentence_source"].split(" (")[0] for m in mails if m["body"])))
    print(f"\n맞춤 메일 초안 {sum(1 for m in mails if m['body'])}통 →", dict(Counter(m["branch"] for m in mails if m["body"])))
    print("글 없음 → 답변만 보냄:", sum(1 for m in mails if "답변만 보냄" in m["note"]),
          "/ 담당자로 전환:", sum(1 for m in mails if "담당자로 전환" in m["note"]),
          "/ 맞춤 메일 생략:", sum(1 for m in mails if "생략" in m["note"]))
    print("같은 회사 수신자 표시:", sum(1 for m in mails if "같은 회사" in m["note"]), "통")
    print("글쓰기 기준·사실 확인 경고:", sum(1 for m in mails if m["lint"]), "통 (0이 아니면 custom_mails.csv의 lint 칸을 보고 고친 뒤 보낼 것)")
    print(f"영업 전달 패키지 {len(handoff)}건 → out/sales_handoff.csv"
          f" (먼저 연락 {sum(1 for h in handoff if h['contact_mode'] == '먼저 연락')} / 회신 오면 연락 {sum(1 for h in handoff if h['contact_mode'] != '먼저 연락')}"
          f" / 이미 진행 중인 사람의 새 행사 {sum(1 for h in handoff if h['sales_status'] != '신규')})")
    print(f"다음에 쓸 글 목록 {len(gap_rows)}개 주제 → out/content_gaps.csv")
    print("답변 재료집 검수표 → out/answer_bank_review.csv")
    print(f"처음 보는 질문 {len(unseen)}종 (2번 이상 나온 답변집 후보 {sum(1 for u in unseen.values() if u['count'] >= 2)}종) → out/answer_bank_candidates.csv")
    print("설문 '도움된 내용' 문장 들어간 메일:", sum(1 for m in mails if "도움이 되었다고" in m["body"]), "통")
    print("답변 재료가 들어간 메일:", sum(1 for m in mails if m.get("answer")),
          "통" + ("" if include_drafts else " (승인된 답변만. 검수 전 답변까지 보려면 --include-drafts)"))


def as_of(send_by, mode):
    """send: 메일 보내는 날까지 발행된 글만 (실제 상황) / today: 오늘까지 발행된 글 전부 (다음 행사 시연용)"""
    return send_by if mode == "send" else date.today()


def _base(r):
    return {k: r[k] for k in ["event_id", "event_name", "email", "name", "company", "title", "consent",
                               "branch", "approval", "send_by", "pre_question", "survey_topic"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", choices=["send", "today"], default="send",
                    help="send: 메일 시점에 있던 글만 (기본) / today: 지금 있는 글 전부")
    ap.add_argument("--include-drafts", action="store_true",
                    help="답변 재료집의 검수 전(draft) 답변도 넣어서 미리 보기")
    a = ap.parse_args()
    main(a.as_of, a.include_drafts)
