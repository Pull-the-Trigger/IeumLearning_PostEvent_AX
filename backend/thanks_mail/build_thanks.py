"""행사별 참석자 감사 메일 초안.

  python backend/thanks_mail/build_thanks.py

입력: data/processed/ 의 profiles.json, events.csv, surveys.csv (backend/data/build_profile.py 결과)
설정: backend/thanks_mail/config.json (발송 기한, 제외 행사, 행사별 링크)
문안: backend/thanks_mail/template.txt (제목·본문·설문 문단 두 가지), signature.txt (서명)
출력: out/thanks_mails.csv (본부장 검토용 초안, status=draft)

- 대상: 각 행사의 참석자(attended=Y) 전원, 수신 동의와 상관없이. 제외 행사(E07 등)는 뺀다.
- 한 사람이 여러 행사에 참석했으면 행사마다 한 통.
- 같은 행사 설문에 이메일을 적고 행사 당일 응답한 사람(현장 QR)은 설문 요청 대신 응답 감사 문단을 넣는다.
"""
import argparse
import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "out" / "thanks_mails.csv"

COLUMNS = ["event_id", "event_name", "email", "name", "company", "title", "consent",
           "mail_type", "survey_included", "sender", "send_by", "status", "subject", "body"]

SURVEY_SLOT = "{설문 문단}"
SIGNATURE_SLOT = "{서명}"
GREETING = "{이름} {직함}님"
BLOCK_ASK, BLOCK_THANKS = "설문 요청", "설문 응답 감사"   # template.txt 아래쪽의 두 설문 문단
BLOCK = re.compile(r"\{(" + BLOCK_ASK + "|" + BLOCK_THANKS + r")\}\n(.*?)\n\{\1 끝\}", re.S)

# 06 글쓰기 기준 검사
BANNED = ["혁신적", "획기적", "압도적", "지금 바로", "놓치지 마세요", "마지막 기회"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
MULTI_BANG = re.compile(r"[!！][^!！]*[!！]")   # 한 통에 느낌표 2개 이상
LEFTOVER = re.compile(r"\{[^{}]*\}")


def norm_email(s):
    return (s or "").strip().lower()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_template(path, signature_path):
    """template.txt → (제목, 본문, {설문 문단 종류: 문단}). 서명은 signature.txt에서 넣는다."""
    text = Path(path).read_text(encoding="utf-8").strip("\n")
    first, _, rest = text.partition("\n")
    if not first.startswith("제목:"):
        sys.exit(f"[오류] {path} 첫 줄은 '제목: ...' 이어야 합니다.")
    blocks = {m.group(1): m.group(2).strip("\n") for m in BLOCK.finditer(rest)}
    for name in (BLOCK_ASK, BLOCK_THANKS):
        if name not in blocks:
            sys.exit(f"[오류] {path}에 {{{name}}} ... {{{name} 끝}} 문단이 없습니다.")
    body = BLOCK.sub("", rest)
    signature = Path(signature_path).read_text(encoding="utf-8").strip("\n")
    body = body.replace(SIGNATURE_SLOT, signature).strip("\n")
    return first[len("제목:"):].strip(), body, blocks


def render(subject_t, body_t, blocks, *, name, title, event_name, event_date, slides, survey, include_survey):
    d = date.fromisoformat(event_date)
    greeting = f"{name} {title}님" if (title or "").strip() else "담당자님"
    body = body_t.replace(GREETING, greeting)
    body = body.replace(SURVEY_SLOT, blocks[BLOCK_ASK if include_survey else BLOCK_THANKS])

    values = {"{행사명}": event_name, "{M월 D일}": f"{d.month}월 {d.day}일",
              "{발표 자료 링크}": slides, "{설문 링크}": survey}
    subject = subject_t
    for k, v in values.items():
        body = body.replace(k, v)
        subject = subject.replace(k, v)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    return subject, body


def lint(text):
    warns = [f"금지 표현 '{w}'" for w in BANNED if w in text]
    if MULTI_BANG.search(text):
        warns.append("느낌표 2개 이상")
    if EMOJI.search(text):
        warns.append("이모지")
    for m in LEFTOVER.findall(text):
        warns.append(f"치환 안 된 자리 {m}")
    return warns


def main():
    ap = argparse.ArgumentParser(description="감사 메일 초안 만들기")
    ap.add_argument("--config", default=HERE / "config.json")
    ap.add_argument("--template", default=HERE / "template.txt")
    ap.add_argument("--signature", default=HERE / "signature.txt")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    # send_by = 발송 기한 (예약 발송은 하지 않음). 기한 안 = 보낸 시각 < send_by
    days_after = int(cfg.get("send_by_days_after", 1))
    by_time = cfg.get("send_by_time", "12:00")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", by_time):
        sys.exit(f"[오류] config.json send_by_time 형식은 HH:MM 입니다: {by_time!r}")
    sender = (cfg.get("sender") or "").strip()
    if not sender:
        sys.exit("[오류] config.json 에 sender(보내는 사람)가 없습니다.")
    exclude = set(cfg.get("exclude_events", []))
    links = cfg.get("links", {})
    for eid, l in links.items():
        for k, url in l.items():
            if "@" in url:
                sys.exit(f"[오류] {eid} {k} 링크에 '@'가 있습니다. 링크에 이메일 등 개인정보를 넣지 마세요: {url}")

    subject_t, body_t, blocks = load_template(args.template, args.signature)

    events = {r["event_id"]: r for r in read_csv(PROCESSED / "events.csv")}
    profiles = json.loads((PROCESSED / "profiles.json").read_text(encoding="utf-8"))

    # 현장 QR 응답: 같은 행사 설문에 이메일을 적고 행사 당일 응답
    onsite = set()
    for s in read_csv(PROCESSED / "surveys.csv"):
        ev, em = events.get(s["event_id"]), norm_email(s.get("email"))
        if ev and em and s.get("response_date") == ev["event_date"]:
            onsite.add((s["event_id"], em))

    targets = []
    for p in profiles:
        for e in p.get("events", []):
            if e.get("attended") == "Y" and e["event_id"] not in exclude:
                targets.append((p, e["event_id"]))

    missing = sorted({eid for _, eid in targets if eid not in events or eid not in links
                      or not links[eid].get("slides") or not links[eid].get("survey")})
    if missing:
        sys.exit(f"[오류] events.csv 또는 config.json links에 없는 행사: {', '.join(missing)}")

    rows, warnings = [], []
    for p, eid in targets:
        ev, email = events[eid], norm_email(p["email"])
        include = (eid, email) not in onsite
        subject, body = render(subject_t, body_t, blocks, name=p["name"], title=p.get("title"),
                               event_name=ev["event_name"], event_date=ev["event_date"],
                               slides=links[eid]["slides"], survey=links[eid]["survey"],
                               include_survey=include)
        send_by = f"{(date.fromisoformat(ev['event_date']) + timedelta(days=days_after)).isoformat()} {by_time}"
        rows.append({"event_id": eid, "event_name": ev["event_name"], "email": email,
                     "name": p["name"], "company": p.get("company") or "", "title": p.get("title") or "",
                     "consent": p.get("consent") or "", "mail_type": "thanks",
                     "survey_included": "Y" if include else "N", "sender": sender, "send_by": send_by,
                     "status": "draft", "subject": subject, "body": body})
        for w in lint(subject + "\n" + body):
            warnings.append(f"{eid}/{email}: {w}")
    rows.sort(key=lambda r: (r["event_id"], r["email"]))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"저장: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print("행사    통수  설문 뺌")   # 한글은 두 칸 폭이라 머리글은 직접 맞춤
    total = skipped = 0
    for eid in sorted({r["event_id"] for r in rows}):
        n = sum(r["event_id"] == eid for r in rows)
        k = sum(r["event_id"] == eid and r["survey_included"] == "N" for r in rows)
        total, skipped = total + n, skipped + k
        print(f"{eid:<4}{n:>8}{k:>8}")
    print(f"합계{total:>8}{skipped:>8}")
    print(f"글쓰기 기준 경고: {len(warnings)}건")
    for w in warnings:
        print(f"  [경고] {w}")


if __name__ == "__main__":
    main()
