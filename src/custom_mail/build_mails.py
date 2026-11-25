"""출석자별 맞춤 메일 초안 + 영업 전달 패키지.

  python src/custom_mail/build_mails.py              # 메일 보내는 날까지 발행된 글만 사용 (실제 상황)
  python src/custom_mail/build_mails.py --as-of today # 지금 있는 글 전부 사용 (다음 행사 시연용)

1. plan_followups로 출석자별 갈래를 정한다 (영업 / 글 안내 / 담당자 / 사실 / 설문 주제 / 감사 메일만)
2. 글을 고른다 — 사전 질문: question_map.json의 article (검수된 짝)
                   처음 보는 질문: AI가 36편 중 고름, 맞는 글 없으면 '없음'
                   설문 주제: 같은 주제 글 중 직함에 맞는 대상 독자의 글
3. 갈래별 문안 틀에 넣는다 — 문장은 사람이 정한 틀만 쓰고 AI는 문장을 쓰지 않는다 (지어내기 방지)
4. 06 글쓰기 기준 검사 (합니다체, 금지 표현, 느낌표·이모지, 제품명 표기)

출력: out/custom_mails.csv (본부장 검토용 초안, v2 + 비교용 v1), out/sales_handoff.csv (영업 담당자용 근거),
      out/mail_compare.csv (기존 v1 vs 새 v2 12통 나란히), out/content_gaps.csv (다음에 쓸 글 목록)
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
sys.path.insert(0, str(ROOT / "src" / "pre_question"))
sys.path.insert(0, str(HERE))
from mail_v2 import render_v2  # noqa: E402
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
        rules = json.loads((ROOT / "src" / "pre_question" / "question_map.json").read_text(encoding="utf-8"))["rules"]
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


def article_block(a, lead):
    return f"{lead}\n「{a['title']}」\n{a['url']}"


def render(row, art, prev_event, send_by):
    name = f"{row['name']} {row['title']}님" if row.get("title") else f"{row['name']} 담당자님"
    q, ev = row["pre_question"], row["event_name"]
    br = row["branch"]
    lines = [f"{name}, 안녕하세요. {SENDER}입니다."]
    # 첫 문단: 왜 연락하는지 한 문장 (06-1)
    why = {"SALES": f"{ev}에서 남겨 주신 내용과 관련해 연락드립니다.",
           "ARTICLE": f"{ev}에 신청하시며 남겨 주신 질문에 답변드리고자 연락드립니다.",
           "STAFF": f"{ev}에 신청하시며 남겨 주신 질문과 관련해 연락드립니다.",
           "FACT": f"{ev}에 신청하시며 남겨 주신 질문에 답변드리고자 연락드립니다.",
           "CUSTOM_TOPIC": f"{ev} 설문에 남겨 주신 관심 주제와 관련해 연락드립니다."}[br]
    lines.append(why)
    if prev_event:
        lines.append(f"지난 {prev_event}에 이어 다시 참석해 주셔서 감사합니다.")
    body = []
    if br == "SALES":
        due = add_business_days(send_by, CONTACT_BUSINESS_DAYS)
        if q:
            body.append(f"신청서에 ‘{q}’라고 물어보셨습니다. 더 정확히 안내드리기 위해 "
                        f"담당자가 {due.month}월 {due.day}일까지 직접 연락드려 회사 상황을 여쭙고 자세히 안내드리겠습니다.")
        elif "설문 연락 희망" in row["sales_triggers"]:
            body.append(f"설문에서 담당자 연락을 요청해 주셨습니다. 담당자가 {due.month}월 {due.day}일까지 직접 연락드리겠습니다.")
        else:
            body.append(f"남겨 주신 내용을 바탕으로 담당자가 {due.month}월 {due.day}일까지 직접 연락드려 필요하신 부분을 여쭙겠습니다.")
        if art:
            body.append(article_block(art, "연락드리기 전에 참고하실 수 있도록 관련 글을 한 편 전해 드립니다."))
    elif br == "ARTICLE":
        body.append(f"신청서에 ‘{q}’라고 물어보셨습니다. 이 질문을 다룬 글을 전해 드립니다.")
        body.append(article_block(art, "").lstrip("\n"))
    elif br == "STAFF":
        body.append(f"신청서에 ‘{q}’라고 물어보셨습니다. 정확한 답변을 드리기 위해 담당자가 확인한 뒤 따로 답변드리겠습니다.")
        if art:
            body.append(article_block(art, "직접적인 답은 아니지만 참고가 될 만한 글을 먼저 전해 드립니다."))
    elif br == "FACT":
        body.append(f"신청서에 ‘{q}’라고 물어보셨습니다. [행사 기록으로 답변 작성 — 기록에 없으면 담당자 확인]")
    elif br == "CUSTOM_TOPIC":
        body.append(article_block(art, f"설문에서 ‘{row['survey_topic']}’에 관한 이야기를 듣고 싶다고 남겨 주셔서, 이 주제를 다룬 글을 전해 드립니다."))
    lines += body
    lines.append("궁금하신 점은 이 메일에 회신해 주십시오.")
    lines.append(f"{SENDER} 드림")
    subject = {"SALES": f"[이음러닝] {ev}에서 남겨 주신 내용 관련 안내",
               "ARTICLE": f"[이음러닝] {ev}에서 남겨 주신 질문에 대한 답변",
               "STAFF": f"[이음러닝] {ev}에서 남겨 주신 질문 관련 안내",
               "FACT": f"[이음러닝] {ev}에서 남겨 주신 질문에 대한 답변",
               "CUSTOM_TOPIC": f"[이음러닝] {ev} 설문에 남겨 주신 관심 주제 관련 글"}[br]
    return subject, "\n\n".join(lines)


def load_staff():
    """담당자 목록(가상, src/custom_mail/staff_directory.csv). 실제 운영 땐 이 표만 바꾸면 된다."""
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


def main(as_of_mode="send"):
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
    # 산업군(내부용, 팀원 data 브랜치 11/25): 영업 전달 패키지에만 쓰고 메일 본문에는 쓰지 않는다
    industry = {}
    pj = PROCESSED / "profiles.json"
    if pj.exists():
        for p in json.loads(pj.read_text(encoding="utf-8")):
            industry[p["email"].strip().lower()] = (p.get("industry_major") or "", p.get("industry_mid") or "")

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
            r = {**r, "branch": "STAFF"}
            note = "맞는 글이 없어 담당자로 전환"
        if r["branch"] == "CUSTOM_TOPIC" and not art:
            note = "주제에 맞는 글 없음 → 맞춤 메일 생략, 관심 분야 기록"
            mails.append({**_base(r), "subject": "", "body": "", "sentence_source": "", "assigned_staff": "", "article": "",
                          "article_reason": art_why, "note": note, "lint": "", "subject_v1": "", "body_v1": ""})
            continue
        subject_v1, body_v1 = render(r, art, prev_event, send_by)
        due = add_business_days(send_by, CONTACT_BUSINESS_DAYS)
        ind_major = industry.get(r["email"], ("", ""))[0]
        rep = None
        if r["branch"] in ("SALES", "STAFF"):
            rep = assign_staff(staff, r["branch"], ind_major if r["branch"] == "SALES" else "", r["company"])
        sv = surveys.get((r["event_id"], r["email"]), {})
        helpful = (sv.get("q4_helpful_content") or "").strip()
        survey_line = f"설문에서 ‘{helpful}’{josa_iga(helpful)} 도움이 되었다고 남겨 주셔서 감사합니다." if helpful else ""
        subject, body, src, co_note = render_v2(r, art, prev_event, due, picker.label(r["pre_question"]),
                                                same_co[(r["event_id"], r["company"])], rep, survey_line)
        warns = lint(subject + "\n" + body)
        mails.append({**_base(r), "subject": subject, "body": body, "sentence_source": src,
                      "assigned_staff": f"{rep['name']} {rep['position']} ({rep['team']})" if rep else "",
                      "article": f"{art['content_id']} {art['title']}" if art else "",
                      "article_reason": art_why, "note": "; ".join(x for x in [note, co_note] if x),
                      "lint": "; ".join(warns), "subject_v1": subject_v1, "body_v1": body_v1})
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
                "contact_due": add_business_days(send_by, CONTACT_BUSINESS_DAYS).isoformat(),
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

    # 기존(v1) vs 새 버전(v2) 비교: 갈래·글 유무·직함군별로 골고루 12통
    seen, cmp_rows = set(), []
    for m in mails:
        k = (m["branch"], bool(m["article"]), any(t in m["title"] for t in ("대표", "전무", "상무", "부사장")), bool(m["pre_question"]))
        if m["body"] and k not in seen and len(cmp_rows) < 12:
            seen.add(k)
            cmp_rows.append({"branch": m["branch"], "name": m["name"], "title": m["title"], "pre_question": m["pre_question"],
                             "v1_subject": m["subject_v1"], "v1_body": m["body_v1"],
                             "v2_subject": m["subject"], "v2_body": m["body"], "v2_sentence_source": m["sentence_source"]})
    with open(OUT / "mail_compare.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        w.writeheader()
        w.writerows(cmp_rows)
    from collections import Counter
    print("문장 출처:", dict(Counter(m["sentence_source"].split(" (")[0] for m in mails if m["body"])))
    print(f"\n맞춤 메일 초안 {sum(1 for m in mails if m['body'])}통 →", dict(Counter(m["branch"] for m in mails if m["body"])))
    print("글 없음으로 생략·전환:", sum(1 for m in mails if "글" in m["note"] and ("전환" in m["note"] or "생략" in m["note"])))
    print("같은 회사 수신자 표시:", sum(1 for m in mails if "같은 회사" in m["note"]), "통")
    print("글쓰기 기준 경고:", sum(1 for m in mails if m["lint"]), "통")
    print(f"영업 전달 패키지 {len(handoff)}건 → out/sales_handoff.csv")
    print(f"다음에 쓸 글 목록 {len(gap_rows)}개 주제 → out/content_gaps.csv")
    print("설문 '도움된 내용' 문장 들어간 메일:", sum(1 for m in mails if "도움이 되었다고" in m["body"]), "통")


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
    main(ap.parse_args().as_of)
