"""행사별 참석자 감사 메일 초안.

  python backend/thanks_mail/build_thanks.py

입력: data/processed/ 의 profiles.json, events.csv, surveys.csv (backend/data/build_profile.py 결과)
설정: backend/thanks_mail/config.json (발송 기한, 제외 행사, 행사별 링크)
문안: backend/thanks_mail/template.txt (제목·본문·설문 문단 두 가지), signature.txt (서명)
출력: out/thanks_mails.csv (본부장 검토용 초안, status=draft)

- 대상: 각 행사의 참석자(attended=Y) 전원, 수신 동의와 상관없이. 제외 행사(E07 등)는 뺀다.
- 한 사람이 여러 행사에 참석했으면 행사마다 한 통.
- 같은 행사 설문에 이메일을 적고 행사 당일 응답한 사람(현장 QR)은 설문 요청 대신 응답 감사 문단을 넣는다.

화면에서 고친 행사별 문안·링크(DB thanks_settings)도 같은 함수로 만든다 (backend/app/thanks.py, backend/db/load.py):
  default_settings() 기본값 / validate_settings() 검사 / render_with_settings() 한 통 만들기
  현장 응답자 감사 문단과 서명은 고정 (fixed_parts()).
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
CONFIG_PATH = HERE / "config.json"
TEMPLATE_PATH = HERE / "template.txt"
SIGNATURE_PATH = HERE / "signature.txt"

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

# 화면에서 문안을 고칠 때 칸별로 쓸 수 있는 자리 표시 (template.txt 와 같은 모양)
PLACEHOLDERS = {
    "subject_template": ["{이름}", "{직함}", "{행사명}", "{M월 D일}"],
    "body_template": ["{이름}", "{직함}", "{행사명}", "{M월 D일}", "{발표 자료 링크}", SURVEY_SLOT],
    # {설문 링크}는 설문 요청 문단에서만 (현장 응답자 메일에는 설문 링크가 들어가지 않게)
    "survey_ask_block": ["{이름}", "{직함}", "{행사명}", "{M월 D일}", "{발표 자료 링크}", "{설문 링크}"],
}
FIELD_LABELS = {"subject_template": "제목", "body_template": "본문", "survey_ask_block": "설문 요청 문단",
                "slides_url": "발표 자료 링크", "survey_url": "설문 링크"}
SETTING_FIELDS = list(FIELD_LABELS)


def norm_email(s):
    return (s or "").strip().lower()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_template(path=TEMPLATE_PATH, signature_path=SIGNATURE_PATH):
    """template.txt → {subject, body, ask, thanks, signature}.

    body 는 {서명} 자리 앞까지 (서명은 render 가 끝에 붙임). 형식이 틀리면 ValueError.
    """
    text = Path(path).read_text(encoding="utf-8").strip("\n")
    first, _, rest = text.partition("\n")
    if not first.startswith("제목:"):
        raise ValueError(f"[오류] {path} 첫 줄은 '제목: ...' 이어야 합니다.")
    blocks = {m.group(1): m.group(2).strip("\n") for m in BLOCK.finditer(rest)}
    for name in (BLOCK_ASK, BLOCK_THANKS):
        if name not in blocks:
            raise ValueError(f"[오류] {path}에 {{{name}}} ... {{{name} 끝}} 문단이 없습니다.")
    body, slot, after = BLOCK.sub("", rest).partition(SIGNATURE_SLOT)
    if not slot or after.strip():
        raise ValueError(f"[오류] {path} 본문은 {SIGNATURE_SLOT} 로 끝나야 합니다 (서명 뒤에는 설문 문단 두 개만).")
    signature = Path(signature_path).read_text(encoding="utf-8").strip("\n")
    return {"subject": first[len("제목:"):].strip(), "body": body.strip("\n"),
            "ask": blocks[BLOCK_ASK], "thanks": blocks[BLOCK_THANKS], "signature": signature}


def render(subject_t, body_t, blocks, *, name, title, event_name, event_date, slides, survey, include_survey,
           signature):
    """한 통 만들기. body_t 는 서명 앞까지, blocks 는 {설문 요청, 설문 응답 감사} 문단."""
    d = date.fromisoformat(event_date)
    has_title = bool((title or "").strip())
    greeting = f"{name} {title}님" if has_title else "담당자님"
    body = body_t.strip("\n") + "\n\n" + signature
    body = body.replace(GREETING, greeting)
    body = body.replace(SURVEY_SLOT, blocks[BLOCK_ASK if include_survey else BLOCK_THANKS])

    values = {"{행사명}": event_name, "{M월 D일}": f"{d.month}월 {d.day}일",
              "{발표 자료 링크}": slides, "{설문 링크}": survey,
              "{이름}": name or "", "{직함}": title.strip() if has_title else ""}
    subject = subject_t
    for k, v in values.items():
        body = body.replace(k, v)
        subject = subject.replace(k, v)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    return subject, body


def read_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fixed_parts():
    """화면에서 고칠 수 없는 부분: (현장 응답자 감사 문단, 서명)."""
    t = load_template()
    return t["thanks"], t["signature"]


def default_settings(event_id):
    """template.txt + config.json 기본 문안·링크 (thanks_settings 한 줄과 같은 모양)."""
    t = load_template()
    links = read_config().get("links", {}).get(event_id, {})
    return {"subject_template": t["subject"], "body_template": t["body"], "survey_ask_block": t["ask"],
            "slides_url": links.get("slides", ""), "survey_url": links.get("survey", "")}


def validate_settings(s):
    """화면에서 보낸 문안·링크 검사. 문제 문구 목록 (비면 통과)."""
    errors = []
    for field in SETTING_FIELDS:
        if not (s.get(field) or "").strip():
            errors.append(f"{FIELD_LABELS[field]} 칸이 비어 있습니다.")
    for field, allowed in PLACEHOLDERS.items():
        unknown = sorted({m for m in LEFTOVER.findall(s.get(field) or "") if m not in allowed})
        if unknown:
            errors.append(f"{FIELD_LABELS[field]}에 쓸 수 없는 자리 표시: {', '.join(unknown)} "
                          f"(쓸 수 있는 것: {' '.join(allowed)})")
    n = (s.get("body_template") or "").count(SURVEY_SLOT)
    if n != 1:
        errors.append(f"본문에 {SURVEY_SLOT} 자리가 한 번 있어야 합니다 (지금 {n}번).")
    for field in ("slides_url", "survey_url"):
        url = (s.get(field) or "").strip()
        if url and not re.fullmatch(r"https?://[^\s@]+", url):
            errors.append(f"{FIELD_LABELS[field]}는 http:// 또는 https:// 로 시작하고 공백·'@'가 없어야 합니다: {url}")
    return errors


def render_with_settings(s, *, name, title, event_name, event_date, include_survey):
    """thanks_settings 한 줄(또는 default_settings)로 한 통 만들기. 현장 응답 감사 문단·서명은 고정."""
    thanks, signature = fixed_parts()
    blocks = {BLOCK_ASK: s["survey_ask_block"].strip("\n"), BLOCK_THANKS: thanks}
    return render(s["subject_template"].strip(), s["body_template"], blocks, name=name, title=title,
                  event_name=event_name, event_date=event_date, slides=s["slides_url"].strip(),
                  survey=s["survey_url"].strip(), include_survey=include_survey, signature=signature)


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
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--template", default=TEMPLATE_PATH)
    ap.add_argument("--signature", default=SIGNATURE_PATH)
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

    try:
        t = load_template(args.template, args.signature)
    except ValueError as e:
        sys.exit(str(e))
    subject_t, body_t, blocks = t["subject"], t["body"], {BLOCK_ASK: t["ask"], BLOCK_THANKS: t["thanks"]}

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
                               include_survey=include, signature=t["signature"])
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
