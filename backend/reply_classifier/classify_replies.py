"""회신 메일 분류 + 처리 할 일 + 답장 초안.

사용법 (레포 루트에서):
  python backend/reply_classifier/classify_replies.py <회신.json 또는 .csv> [--out out/reply_results]

입력: 회신 메일 목록. 필요한 열은 sender_email, subject, body 세 개뿐이다
     (in_reply_to, reply_id가 있으면 같이 쓴다). 다른 열은 무시한다.
보조 데이터: data/processed/profiles.json, events.csv (build_profile.py가 만든 것)
     → 명단이 바뀌어도 build_profile.py만 다시 돌리면 이 코드는 그대로 동작한다.

출력: <out>.json, <out>.csv — 분류, 근거, 처리 할 일, 승인 방식, 답장 초안.
모든 답장은 '초안'이다. 본부장 승인 전에는 발송하지 않는다 (글쓰기 기준 06).
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import classify_by_rules  # noqa: E402
from llm import classify_by_llm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
EXEC_TITLES = ("대표", "전무", "부사장", "상무", "CTO", "CEO", "본부장", "실장", "임원", "이사")
SALES_REPLY_BUSINESS_DAYS = 3  # 인터뷰 7번: 영업일 3일 목표


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")  # .env가 컴퓨터 환경변수보다 우선


def load_replies(path):
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        return data["replies"] if isinstance(data, dict) else data
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_profiles():
    profiles = json.loads((PROCESSED / "profiles.json").read_text(encoding="utf-8"))
    return {p["email"].strip().lower(): p for p in profiles}


def load_events():
    with open(PROCESSED / "events.csv", encoding="utf-8-sig", newline="") as f:
        return {r["event_id"]: r for r in csv.DictReader(f)}


def add_business_days(d, n):
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def profile_summary(p):
    if not p:
        return "명단에 없는 주소"
    evs = ", ".join(f"{e['event_name']}({'참석' if e['attended'] == 'Y' else '불참'})" for e in p["events"])
    qs = "; ".join(e["pre_question"] for e in p["events"] if e.get("pre_question"))
    return (f"{p['name']} / {p['company']} / {p['title']} / 수신 동의 {p['consent']}\n"
            f"참가 행사: {evs}\n사전 질문: {qs or '없음'}")


def decide_actions(cat, p, reasons, today):
    """분류 → 처리 할 일. 인터뷰 기준(7~10번)과 회의 결정만 반영한다."""
    consent = (p or {}).get("consent") == "Y"
    actions, flags = [], []
    if cat == "SALES":
        due = add_business_days(today, SALES_REPLY_BUSINESS_DAYS)
        actions += ["영업 담당자에게 전달 (근거: 참석 행사·사전 질문·설문·보낸 연락)",
                    "이 사람의 정기 발송 중단",
                    f"영업 담당자 연락 기한 {due.isoformat()} — 기한 지나면 담당자 리마인더"]
        if any("자료·소개서" in r for r in reasons):
            actions.append("요청한 자료·소개서는 마케팅이 바로 발송하고 기록")
    elif cat == "MATERIAL":
        actions += ["요청 자료 바로 발송 + 발송 기록"]
        flags.append("소개서 요청 시 영업 판단 참고 표시")
    elif cat == "FACT":
        actions += ["확보된 사실 정보로 답장 초안 작성 → 본부장 승인",
                    "확보 정보에 답이 없으면 담당자 확인으로 전환 (AI가 지어내지 않음)"]
    elif cat == "STAFF":
        actions += ["담당자 확인 후 답변 (할 일 등록)",
                    "AI 초안은 근거 글이 있을 때만, 담당자 화면에만 표시"]
    elif cat == "UNSUBSCRIBE":
        actions += ["수신 동의 상태를 N으로 변경, 이후 정기 발송 제외"]
    elif cat == "AUTO_REPLY":
        actions += ["처리 없음 (재발송·반복 연락 안 함)"]
    elif cat == "THANKS_ONLY":
        actions += ["처리 종료 (답장 안 함)"]
    else:
        actions += ["담당자 확인 (분류 불가)"]

    if p is None:
        flags.append("명단에 없는 주소 — 사람 확인 필요")
    if not consent and cat in ("FACT", "MATERIAL", "STAFF", "SALES"):
        flags.append("수신 미동의: 답장에 서비스 소개·다음 행사·뉴스레터 권유 넣지 말 것")
    title = (p or {}).get("title", "")
    single = any(k in title for k in EXEC_TITLES)
    approval = "한 통씩 승인 (대표·임원)" if single else "행사별 묶음 승인"
    return actions, flags, approval


def draft_reply(cat, p, today):
    """사람이 고칠 출발점만 만든다. 사실·정책 내용은 쓰지 않는다."""
    name = f"{p['name']} {p['title']}님" if p else "고객님"
    sign = "\n\n이음러닝 마케팅본부장 드림"
    if cat == "SALES":
        due = add_business_days(today, SALES_REPLY_BUSINESS_DAYS)
        return (f"{name}, 회신 주셔서 감사합니다.\n말씀하신 내용은 담당자가 확인해 "
                f"{due.month}월 {due.day}일까지 직접 연락드리겠습니다." + sign)
    if cat == "MATERIAL":
        return f"{name}, 요청하신 자료를 첨부해 드립니다.\n[자료 첨부/링크]" + sign
    if cat == "STAFF":
        return (f"{name}, 회신 주셔서 감사합니다.\n문의하신 내용은 담당자가 확인한 뒤 "
                "따로 답변드리겠습니다." + sign)
    if cat == "FACT":
        return f"{name}, 문의 주셔서 감사합니다.\n[확보된 정보로 답변 — 정보가 없으면 담당자 확인]" + sign
    return ""


def run(in_path, out_stem, today):
    load_env()
    profiles, _events = load_profiles(), load_events()
    results = []
    for i, r in enumerate(load_replies(in_path), 1):
        email = (r.get("sender_email") or "").strip().lower()
        p = profiles.get(email)
        subject, body = r.get("subject", ""), r.get("body", "")
        res = classify_by_rules(subject, body)
        if res["category"] == "AMBIGUOUS":
            llm = classify_by_llm(subject, body, profile_summary(p))
            if llm:
                res = llm
            else:
                res = {**res, "category": "STAFF", "reasons": res["reasons"] + ["AI 키 없음 → 담당자"]}
        actions, flags, approval = decide_actions(res["category"], p, res["reasons"], today)
        results.append({
            "reply_id": r.get("reply_id") or f"R{i:03d}",
            "sender_email": email,
            "sender": f"{p['name']} / {p['company']} / {p['title']}" if p else "",
            "consent": (p or {}).get("consent", ""),
            "category": res["category"],
            "source": res["source"],
            "confidence": res["confidence"],
            "needs_human": res["needs_human"] or res["category"] == "STAFF",
            "reasons": res["reasons"],
            "actions": actions,
            "flags": flags,
            "approval": approval,
            "draft_reply": draft_reply(res["category"], p, today),
        })
    out = Path(out_stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out.with_suffix(".csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        cols = list(results[0].keys()) if results else []
        w.writerow(cols)
        for x in results:
            w.writerow([" | ".join(v) if isinstance(v, list) else v for v in x.values()])
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=str(ROOT / "out" / "reply_results"))
    ap.add_argument("--today", default=None, help="기준일 YYYY-MM-DD (기본: 오늘)")
    a = ap.parse_args()
    today = date.fromisoformat(a.today) if a.today else date.today()
    res = run(a.input, a.out, today)
    print(f"{len(res)}건 분류 완료 → {a.out}.json / .csv")
