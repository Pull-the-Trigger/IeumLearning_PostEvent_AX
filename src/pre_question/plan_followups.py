"""출석자별 후속 연락 계획: 영업 / 글 안내 / 담당자 / 맞춤(설문 주제) / 감사 메일만.

사용법 (레포 루트에서):
  python src/pre_question/plan_followups.py [--out out/followup_plan]

입력: data/processed/ 의 participation.csv, surveys.csv, interactions.csv, events.csv
     (build_profile.py가 만든 표준 표 — 명단 열 이름이 달라도 여기선 같은 이름)
설정: src/pre_question/question_map.json (질문 → 갈래)

판단 순서 (11/25 팀 결정):
  1. 영업 신호가 하나라도 있으면 SALES
     - 설문 연락 희망 Y / 설문 도입 검토 Y 또는 검토 중
     - 행사장 견적·소개서·미팅 요청 (후속연락기록)
     - 사전 질문이 영업 갈래 (도입·과정·비용, 또는 상대 회사 정보 필요)
  2. 사전 질문이 있으면 그 갈래 (ARTICLE / STAFF / FACT) — classify.py
     사전 문장과 다르게 써도 AI가 뜻으로 판단, 키 없으면 STAFF. "없습니다" 같은 글은 질문 없음
  3. 질문 없음 + 설문 '듣고 싶은 주제' 있음 + 수신 동의 → CUSTOM_TOPIC (주제로 글 1편)
  4. 아무것도 안 남김, 또는 미동의자인데 질문 없음 → THANKS_ONLY (감사 메일만)
출력: <out>.csv (1인 1행사 1행), <out>_contact_needed.csv (연락 희망했지만 이메일 없는 설문)
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
EXEC_TITLES = ("대표", "전무", "부사장", "상무", "CTO", "CEO", "본부장", "실장", "임원", "이사", "공장장")
SALES_WORDS_IN_RECORD = ("견적", "미팅", "소개서", "제안")


def read(name):
    with open(PROCESSED / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")  # .env가 컴퓨터 환경변수보다 우선


def add_business_days(d, n):
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def main(out_stem):
    load_env()
    from classify import classify  # .env를 읽은 뒤에 불러온다
    events = {e["event_id"]: e for e in read("events.csv")}
    parts = [p for p in read("participation.csv") if p["attended"] == "Y" and p.get("is_test") != "True"]
    surveys = read("surveys.csv")
    inter = read("interactions.csv")
    sv = {}
    for s in surveys:
        if s.get("email"):
            sv[(s["event_id"], s["email"].strip().lower())] = s
    rec = {}
    for i in inter:
        if i.get("email"):
            rec.setdefault((i["event_id"], i["email"].strip().lower()), []).append(i)

    rows = []
    for p in parts:
        k = (p["event_id"], p["email"].strip().lower())
        s, recs = sv.get(k), rec.get(k, [])
        q = (p.get("pre_question") or "").strip()
        topic = (s or {}).get("q5_wanted_topic", "").strip()
        consent = p.get("consent") == "Y"

        triggers = []
        if s and s.get("q7_contact_wish") == "Y":
            triggers.append("설문 연락 희망")
        if s and s.get("q6_adoption") in ("Y", "REVIEW"):
            triggers.append("설문 도입 검토" + ("(검토 중)" if s["q6_adoption"] == "REVIEW" else ""))
        for i in recs:
            txt = f"{i.get('memo', '')} {i.get('result', '')}"
            if any(w in txt for w in SALES_WORDS_IN_RECORD):
                triggers.append(f"현장·후속 기록: {i.get('memo', '')}")
        c = classify(q) if q else {"branch": "NONE", "reason": "", "source": ""}
        q_branch, q_why, q_src = c["branch"], c["reason"], c["source"]
        if q_branch == "NONE":
            q = ""  # "없습니다" 같은 글은 질문 없는 사람과 똑같이 처리
        if q_branch == "SALES":
            triggers.append(f"사전 질문: {q_why}")

        if triggers:
            branch, mail = "SALES", "맞춤 메일(되짚기+참고 글+'담당자가 ○일까지 연락') + 영업 전달 + 정기 발송 중단"
        elif q:
            branch = q_branch
            mail = {"ARTICLE": "맞춤 메일(되짚기+글 1편, 맞는 글 없으면 담당자)",
                    "STAFF": "맞춤 메일(되짚기+참고 글+'담당자가 따로 답변') + 할 일 등록",
                    "FACT": "맞춤 메일(되짚기+행사 기록으로 사실 답변) — 기록에 없으면 담당자"}[q_branch]
        elif topic and consent:
            branch, mail = "CUSTOM_TOPIC", "맞춤 메일(설문 주제로 글 1편)"
        else:
            branch, mail = "THANKS_ONLY", "감사 메일만"

        ev = events.get(p["event_id"], {})
        due = ""
        if branch != "THANKS_ONLY" and ev.get("event_date"):
            due = add_business_days(date.fromisoformat(ev["event_date"]), 3).isoformat()
        title = p.get("title", "")
        rows.append({
            "event_id": p["event_id"], "event_name": ev.get("event_name", ""),
            "email": k[1], "name": p["name"], "company": p["company"], "title": title,
            "consent": p.get("consent", ""), "pre_question": q, "survey_topic": topic,
            "branch": branch, "sales_triggers": " | ".join(triggers),
            "question_reason": q_why, "question_source": q_src, "mail": mail,
            "send_by": due,
            "approval": ("감사 메일 문안 1회 확인" if branch == "THANKS_ONLY"
                         else "한 통씩 승인" if (any(t in title for t in EXEC_TITLES) or "설문 연락 희망" in triggers)
                         else "묶음 승인"),
            "content_limit": "" if consent else "미동의: 질문 답 + 관련 글 1편까지만 (서비스 소개·다음 행사·뉴스레터 금지)",
            "survey_done": "Y" if s else "N",
        })

    out = Path(out_stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    missing = [s for s in surveys if s.get("q7_contact_wish") == "Y" and not s.get("email")]
    with open(f"{out}_contact_needed.csv", "w", encoding="utf-8-sig", newline="") as f:
        cols = ["survey_id", "event_id", "response_date", "q5_wanted_topic", "q6_adoption"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(missing)

    c = Counter(r["branch"] for r in rows)
    print(f"출석 {len(rows)}건 → " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"연락처 확인 필요(연락 희망·이메일 없음) {len(missing)}건")
    by_ev = Counter((r["event_id"], r["branch"]) for r in rows)
    for e in sorted(events):
        print(e, {b: by_ev[(e, b)] for b in ["SALES", "ARTICLE", "STAFF", "FACT", "CUSTOM_TOPIC", "THANKS_ONLY"]})
    unknown = [r for r in rows if r["question_source"] in ("default", "llm")]
    if unknown:
        print(f"질문 사전에 없는 질문 {len(unknown)}건 — question_map.json에 추가 검토")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out" / "followup_plan"))
    main(ap.parse_args().out)
