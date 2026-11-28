"""이음러닝 행사 후속 관리: 원본 엑셀 → 표준 스키마 → 이메일 기준 통합 프로필.

실행:
    python backend/data/build_profile.py              # 변환 + 산업군 분류(키가 있을 때) + 통합 프로필 + 확인 출력
    python backend/data/build_profile.py --no-classify  # LLM 산업군 분류 없이 실행
    python backend/data/build_profile.py --make-test  # 테스트 명단(E07) 생성

원본(data/raw/)은 읽기만 하고, 결과는 data/processed/ 에 저장합니다.
"""
import argparse
import glob
import json
import os
import re
import sys
import unicodedata

import pandas as pd

import classify_industry as ci

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 저장소 루트 (backend/data/ 의 두 단계 위)
MAP = json.load(open(os.path.join(ROOT, "backend", "data", "mapping.json"), encoding="utf-8"))
TEST_FILE_NAME = "01_참가자명단_E07_테스트행사.xlsx"

# ---------------------------------------------------------------- 테스트 명단 정의
# (원본 열 이름, 기대 표준 열, 기대 매칭 단계). 표준 열이 None 이면 오류 목록에 남아야 함.
TEST_COLUMNS = [
    ("No", "(무시)", "ignore"),
    ("참가자명", "name", "③ 핵심 단어"),
    ("소속", "company", "① 정확 일치"),
    ("직 급", "title", "② 기호·띄어쓰기 제거"),
    ("메일주소", "email", "② 기호·띄어쓰기 제거"),
    ("사전질문", "pre_question", "② 기호·띄어쓰기 제거"),
    ("참석 체크", "attended", "③ 핵심 단어"),
    ("이메일 수신 동의", "consent", "③ 핵심 단어"),
    ("비고", "note", "① 정확 일치"),
    ("관심 분야", None, "오류"),
]
# 원본 값 행 + 변환 후 기대값 (email=None 행은 필수값 누락 → 프로필에서 빠져야 함)
TEST_ROWS = [
    {"raw": [1, "테스트일", "(주)테스트상사", "팀장", " Test01@Test.example ", "도입 사례가 궁금합니다.", "O", "동의", "현장 등록", "AI 교육"],
     "expect": {"email": "test01@test.example", "name": "테스트일", "company": "테스트상사", "title": "팀장",
                "attended": "Y", "consent": "Y", "note": "현장 등록"}},
    {"raw": [2, "테스트이", "테스트 솔루션㈜", "과장", "test02@test.example", None, "X", "미동의", None, "보안"],
     "expect": {"email": "test02@test.example", "name": "테스트이", "company": "테스트솔루션", "title": "과장",
                "attended": "N", "consent": "N", "note": None}},
    {"raw": [3, "테스트삼", "주식회사 테스트랩", "대표", "test03@test.example", None, "O", "동의", "명함 교환", None],
     "expect": {"email": "test03@test.example", "name": "테스트삼", "company": "테스트랩", "title": "대표",
                "attended": "Y", "consent": "Y", "note": "명함 교환"}},
    {"raw": [4, "테스트사", "테스트상사", "사원", None, None, "O", "동의", "이메일 미기재", None],
     "expect": None},
]


def make_test_file(raw_dir):
    path = os.path.join(raw_dir, TEST_FILE_NAME)
    df = pd.DataFrame([r["raw"] for r in TEST_ROWS], columns=[c for c, _, _ in TEST_COLUMNS])
    df.to_excel(path, index=False, sheet_name="신청자")
    print(f"테스트 명단을 만들었습니다: {os.path.relpath(path, ROOT)}")


# ---------------------------------------------------------------- 공통 도구
errors = []  # {file, row, column, reason}


def err(file, reason, row=None, column=None):
    errors.append({"file": file, "row": row, "column": column, "reason": reason})


def norm(s):
    """띄어쓰기·대소문자·기호를 지운 비교용 문자열."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(s).lower())


def is_blank(v):
    """None·NaN·pd.NA·NaT 모두 빈칸으로 봄 (pandas 2.x/3.x 공통)."""
    return v is None or (not isinstance(v, (list, dict, str)) and bool(pd.isna(v)))


def py(v):
    """JSON 에 넣을 값: 빈칸은 None, numpy 숫자는 파이썬 숫자로."""
    if is_blank(v):
        return None
    return v.item() if hasattr(v, "item") else v


def records(df):
    """DataFrame → [dict]. 빈칸은 pandas 버전과 상관없이 항상 None."""
    return [{k: py(v) for k, v in r.items()} for r in df.to_dict("records")]


def clean(v):
    if is_blank(v):
        return None
    v = str(v).strip()
    return v or None


def norm_company(s):
    s = clean(s)
    if s is None:
        return None
    for w in MAP["company_remove"]:
        s = s.replace(w, "")
    return re.sub(r"\s", "", s) or None


def norm_email(s):
    s = clean(s)
    return s.lower() if s else None


def validate(field, values):
    """④ 값으로 검증. 검증 규칙이 없는 열은 통과."""
    vals = [clean(v) for v in values]
    vals = [v for v in vals if v is not None]
    if not vals:
        return field not in ("email", "attended", "consent")
    if field == "email":
        return sum("@" in v for v in vals) / len(vals) >= 0.8
    if field in ("attended", "consent"):
        return all(v in MAP["values"][field] for v in vals)
    return True


def match_column(col, values, table):
    """열 하나를 표준 열로. 반환 (field 또는 None, 단계 또는 실패 이유)."""
    dic = MAP["columns"][table]
    if col in dic:  # ①
        return dic[col], "① 정확 일치"
    n = norm(col)
    for k, f in dic.items():  # ②
        if norm(k) == n:
            if validate(f, values):
                return f, "② 기호·띄어쓰기 제거"
            return None, f"② '{k}'와 같지만 {f} 값 검증 실패"
    if table != "participation":
        return None, "사전에 없는 열"
    tried = []
    for kw in MAP["keywords"]:  # ③ → ④, 실패하면 다음 후보
        hit = any(norm(w) in n for w in kw["words"]) or any(n.endswith(s) for s in kw.get("suffix", []))
        if not hit:
            continue
        if validate(kw["field"], values):
            return kw["field"], "③ 핵심 단어"
        tried.append(kw["field"])
    if tried:
        return None, f"핵심 단어 후보 {tried} 모두 값 검증 실패"
    return None, "사전·핵심 단어 어디에도 없는 열"


def map_columns(df, table, fname):
    """반환: {원본 열: 표준 열}, {원본 열: (표준 열 또는 None, 단계)}."""
    mapping, steps, used = {}, {}, {}
    for col in df.columns:
        c = str(col).strip()
        if table == "participation" and c in MAP["ignore_columns"]:  # 03 발행글의 '번호'는 content_id 로 씀
            steps[c] = ("(무시)", "ignore")
            continue
        field, step = match_column(c, df[col].tolist(), table)
        if field is None:
            err(fname, f"열 변환 실패: {step}", column=c)
            steps[c] = (None, "오류")
        elif field in used:
            err(fname, f"열 변환 실패: '{used[field]}' 열이 이미 {field}로 변환됨", column=c)
            steps[c] = (None, "오류")
        else:
            mapping[col], steps[c], used[field] = field, (field, step), c
    return mapping, steps


def convert_value(v, kind, fname, row, col):
    v = clean(v)
    if v is None:
        return None
    out = MAP["values"][kind].get(v)
    if out is None:
        err(fname, f"값 사전에 없는 값 '{v}'", row=row, column=col)
    return out


def read_table(path, table, sheet=0):
    fname = os.path.basename(path)
    df = pd.read_excel(path, sheet_name=sheet, dtype=object)
    mapping, _ = map_columns(df, table, fname)
    return df[list(mapping)].rename(columns=mapping), fname


def to_int(v):
    v = clean(v)
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


# ---------------------------------------------------------------- 표 변환
def load_participation(raw_dir):
    rows, steps_by_file, no_email = [], {}, []
    for path in sorted(glob.glob(os.path.join(raw_dir, "01_*.xlsx"))):
        fname = os.path.basename(path)
        m = re.search(r"_(E\d+)_", fname)
        if not m:
            err(fname, "파일 이름에서 행사 ID(E00)를 찾지 못함")
            continue
        event_id = m.group(1)
        df = pd.read_excel(path, dtype=object)
        mapping, steps = map_columns(df, "participation", fname)
        steps_by_file[fname] = steps
        if "email" not in mapping.values():
            err(fname, "이메일 열을 찾지 못함 → 통합 프로필에 넣을 수 없음")
            no_email.append(fname)
            continue
        inv = {v: k for k, v in mapping.items()}
        for i, r in df.iterrows():
            excel_row = i + 2  # 머리글이 1행
            get = lambda f: r[inv[f]] if f in inv else None
            rec = {
                "event_id": event_id,
                "email": norm_email(get("email")),
                "name": clean(get("name")),
                "company": norm_company(get("company")),
                "company_raw": clean(get("company")),
                "title": clean(get("title")),
                "pre_question": clean(get("pre_question")),
                "attended": convert_value(get("attended"), "attended", fname, excel_row, inv.get("attended")),
                "consent": convert_value(get("consent"), "consent", fname, excel_row, inv.get("consent")),
                "note": clean(get("note")),
                "source_file": unicodedata.normalize("NFC", fname),  # Mac 파일 이름의 한글 자모 분리(NFD) 정리
                "source_row": excel_row,
                "is_test": event_id in MAP["test_events"],
            }
            for f in MAP["required"]["participation"]:
                if rec[f] is None:
                    err(fname, f"필수값 누락: {f}", row=excel_row, column=inv.get(f, f))
            rows.append(rec)
    cols = ["event_id", "email", "name", "company", "company_raw", "title", "pre_question",
            "attended", "consent", "note", "source_file", "source_row", "is_test"]
    return pd.DataFrame(rows, columns=cols), steps_by_file, no_email


def load_events(raw_dir):
    path = glob.glob(os.path.join(raw_dir, "00_*.xlsx"))[0]
    df, _ = read_table(path, "event")
    df = df.apply(lambda s: s.map(clean))
    sent = df["thanks_mail_date"].fillna("").str.match(r"\d{4}-\d{2}-\d{2}")
    df["thanks_mail_sent"] = sent.map({True: "Y", False: "N"})
    df.loc[~sent, "thanks_mail_date"] = None
    for c in ("applied_count", "attended_count", "survey_count"):
        df[c] = df[c].map(to_int)
    return df[["event_id", "event_name", "event_date", "event_type", "applied_count", "attended_count",
               "thanks_mail_date", "thanks_mail_sent", "survey_count", "note"]]


def load_surveys(raw_dir):
    path = glob.glob(os.path.join(raw_dir, "02_*.xlsx"))[0]
    df, fname = read_table(path, "survey", sheet="응답")
    out = []
    for i, r in df.iterrows():
        row = i + 2
        out.append({
            "survey_id": f"S{i + 1:03d}",
            "event_id": clean(r.get("event_id")),
            "response_date": clean(r.get("response_date")),
            "q1_satisfaction": to_int(r.get("q1_satisfaction")),
            "q2_helpfulness": to_int(r.get("q2_helpfulness")),
            "q3_recommend": to_int(r.get("q3_recommend")),
            "q4_helpful_content": clean(r.get("q4_helpful_content")),
            "q5_wanted_topic": clean(r.get("q5_wanted_topic")),
            "q6_adoption": convert_value(r.get("q6_adoption"), "adoption", fname, row, "Q6 도입 검토"),
            "q7_contact_wish": convert_value(r.get("q7_contact_wish"), "yes_no", fname, row, "Q7 연락 희망"),
            "email": norm_email(r.get("email")),
        })
    return pd.DataFrame(out)


def load_interactions(raw_dir, part):
    path = glob.glob(os.path.join(raw_dir, "04_*.xlsx"))[0]
    df, fname = read_table(path, "interaction")
    df = df.apply(lambda s: s.map(clean))
    df["company"] = df["company"].map(norm_company)
    key = part.dropna(subset=["email"]).groupby(["event_id", "name", "company"])["email"].unique()
    emails = []
    for i, r in df.iterrows():
        found = key.get((r["event_id"], r["name"], r["company"]))
        if found is None or len(found) == 0:
            err(fname, "참가자 명단에서 (행사, 이름, 회사)가 같은 사람을 찾지 못함", row=i + 2)
            emails.append(None)
        elif len(found) > 1:
            err(fname, f"같은 (행사, 이름, 회사) 참가자가 {len(found)}명이라 연결하지 않음", row=i + 2)
            emails.append(None)
        else:
            emails.append(found[0])
    df["email"] = emails
    df.insert(0, "interaction_id", [f"I{i + 1:03d}" for i in range(len(df))])
    return df[["interaction_id", "event_id", "name", "company", "contact_date", "method", "memo", "result", "email"]]


def load_contents(raw_dir):
    path = glob.glob(os.path.join(raw_dir, "03_*.xlsx"))[0]
    df, _ = read_table(path, "content")
    df = df.apply(lambda s: s.map(clean))
    df["content_id"] = df["content_id"].map(lambda v: f"C{to_int(v):03d}")
    return df[["content_id", "published_date", "channel", "title", "topic", "audience", "url"]]


# ---------------------------------------------------------------- 통합
def event_order(part, events):
    dates = dict(zip(events["event_id"], events["event_date"]))
    return part.assign(_d=part["event_id"].map(dates).fillna("9999"), _e=part["event_id"]).sort_values(["_d", "_e", "source_row"])


def build_customers(part, events):
    p = event_order(part.dropna(subset=["email"]), events)
    g = p.groupby("email", sort=False)
    last = g.last()  # 가장 최근 행사 값 (빈 값은 건너뜀)
    cust = pd.DataFrame({
        "email": last.index,
        "name": last["name"].values,
        "company": last["company"].values,
        "company_key": last["company"].values,  # Company 표와 연결하는 키 (정규화된 회사명)
        "title": last["title"].values,
        "consent": last["consent"].values,
        "first_event_id": g["event_id"].first().values,
        "last_event_id": g["event_id"].last().values,
    })
    return cust.sort_values("email").reset_index(drop=True)


def build_companies(part, customers, ksic, classify=True):
    """Customer 의 company_key 로 회사 1개 1행. 산업군은 classify_industry 의 순서대로 채움."""
    cust = customers.dropna(subset=["company_key"])
    rows = []
    for key, g in cust.groupby("company_key", sort=True):
        raw = part.loc[part["company"] == key, "company_raw"].dropna()
        domains = g["email"].str.split("@").str[-1]
        rows.append({
            "company_key": key,
            "company_name": raw.value_counts().index[0] if len(raw) else key,
            "domain": domains.value_counts().index[0] if len(domains) else None,
        })
    comp = pd.DataFrame(rows, columns=["company_key", "company_name", "domain"])

    manual, llm = ci.load_manual(), ci.load_llm()
    if classify:
        todo = [r for r in records(comp) if r["company_key"] not in manual and r["company_key"] not in llm]
        print(f"\n■ 산업군 LLM 분류: 확정 사전 {sum(k in manual for k in comp['company_key'])}개, "
              f"지난 LLM 결과 {sum(k in llm for k in comp['company_key'] if k not in manual)}개, 새로 분류 {len(todo)}개")
        new = ci.classify(todo, ksic)
        if new:
            llm.update(new)
            ci.save_llm(llm)
            print(f"  → {os.path.relpath(ci.LLM_PATH, ROOT)} 에 {len(new)}개 저장")
    res = ci.resolve(comp["company_key"].tolist(), manual, llm, ksic, err)
    comp["industry_major"] = comp["company_key"].map(lambda k: res[k][0])
    comp["industry_mid"] = comp["company_key"].map(lambda k: res[k][1])
    comp["industry_source"] = comp["company_key"].map(lambda k: res[k][2])
    return comp


def build_profiles(part, events, surveys, interactions, companies=None):
    names = dict(zip(events["event_id"], events["event_name"]))
    dates = dict(zip(events["event_id"], events["event_date"]))
    ind = {} if companies is None else {
        r["company_key"]: (r["industry_major"], r["industry_mid"]) for r in records(companies)}
    cust = build_customers(part, events)
    p = event_order(part.dropna(subset=["email"]), events)
    pg = {k: v for k, v in p.groupby("email")}
    sg = {k: v for k, v in surveys.dropna(subset=["email"]).groupby("email")} if len(surveys) else {}
    ig = {k: v for k, v in interactions.dropna(subset=["email"]).groupby("email")} if len(interactions) else {}

    def recs(df, drop):
        return [] if df is None else records(df.drop(columns=drop))

    profiles = []
    for c in records(cust):
        ev = pg[c["email"]]
        c.pop("company_key")  # profiles.json 에는 기존 필드 + 산업군 2개만
        major, mid = ind.get(c["company"], (None, None))
        base = {}
        for k, v in c.items():
            base[k] = v
            if k == "company":  # 내부용 산업군 (고객 메일 문장에는 쓰지 않음)
                base["industry_major"], base["industry_mid"] = major, mid
        profiles.append({
            **base,
            "applied_count": int(len(ev)),
            "attended_count": int((ev["attended"] == "Y").sum()),
            "events": [{
                "event_id": r["event_id"],
                "event_name": py(names.get(r["event_id"])) or re.sub(r"^01_참가자명단_E\d+_|\.xlsx$", "", r["source_file"]),
                "event_date": py(dates.get(r["event_id"])),
                "attended": r["attended"], "pre_question": r["pre_question"], "note": r["note"],
            } for r in records(ev)],
            "surveys": recs(sg.get(c["email"]), ["email"]),
            "interactions": recs(ig.get(c["email"]), ["email", "name", "company"]),
        })
    return profiles


# ---------------------------------------------------------------- 확인 출력
def check(label, expected, actual):
    ok = expected == actual
    print(f"  [{'OK' if ok else 'FAIL'}] {label}: 기대 {expected} / 실제 {actual}")
    return ok


def check_counts(part, customers, surveys, interactions, profiles):
    print("\n■ 원본 6개 행사 확인")
    att = part[part["attended"] == "Y"]
    per = att.groupby("email").size()
    attendee_consent = customers[customers["email"].isin(per.index)]["consent"]
    no_mail = surveys["email"].isna()
    res = [
        check("신청", 306, len(part)),
        check("참석", 250, len(att)),
        check("실제 참석자(명)", 232, att["email"].nunique()),
        check("2회 이상 참석(명)", 18, int((per >= 2).sum())),
        check("참석자 수신 동의 Y(명)", 174, int((attendee_consent == "Y").sum())),
        check("참석자 수신 동의 N(명)", 58, int((attendee_consent == "N").sum())),
        check("설문", 45, len(surveys)),
        check("설문 중 이메일 없음", 20, int(no_mail.sum())),
        check("이메일 없음 중 연락 희망", 8, int((no_mail & (surveys["q7_contact_wish"] == "Y")).sum())),
        check("후속연락기록", 25, len(interactions)),
        check("후속연락기록 중 참가자 연결", 25, int(interactions["email"].notna().sum())),
        check("profiles.json 인원 (참석자 + 신청만 한 사람)", "283 = 232 + 51",
              f"{len(profiles)} = {sum(p['attended_count'] > 0 for p in profiles)}"
              f" + {sum(p['attended_count'] == 0 for p in profiles)}"),
    ]
    return all(res)


def check_test(steps_by_file, test_part, test_profiles, profiles):
    print("\n■ 테스트 명단(E07) 확인")
    steps = steps_by_file.get(TEST_FILE_NAME)
    if steps is None:
        print(f"  [FAIL] {TEST_FILE_NAME} 이 없습니다. --make-test 로 만들어 주세요.")
        return False
    col_errors = {e["column"] for e in errors if e["file"] == TEST_FILE_NAME and e["row"] is None}
    res = []
    print("  · 열 이름 변환")
    for col, field, step in TEST_COLUMNS:
        if field is None:
            got = "오류 목록" if col in col_errors else str(steps.get(col))
            res.append(check(f"'{col}'", "오류 목록", got))
        else:
            got_field, got_step = steps.get(col, (None, "없음"))
            res.append(check(f"'{col}'", f"{field} / {step}", f"{got_field} / {got_step}"))
    print("  · 필수값 누락")
    missing = [e for e in errors if e["file"] == TEST_FILE_NAME and e["reason"] == "필수값 누락: email"]
    res.append(check("이메일 없는 행이 오류 목록에", 1, len(missing)))
    print("  · 통합 프로필 (profiles_test.json)")
    expects = [r["expect"] for r in TEST_ROWS if r["expect"]]
    res.append(check("테스트 프로필 수", len(expects), len(test_profiles)))
    by_mail = {p["email"]: p for p in test_profiles}
    for e in expects:
        p = by_mail.get(e["email"])
        if p is None:
            res.append(check(e["email"], "프로필 있음", "없음"))
            continue
        ev = p["events"][0] if p["events"] else {}
        got = {"email": p["email"], "name": p["name"], "company": p["company"], "title": p["title"],
               "attended": ev.get("attended"), "consent": p["consent"], "note": ev.get("note")}
        res.append(check(f"{e['email']} 값 변환", e, got))
        res.append(check(f"{e['email']} 행사", ["E07"], [x["event_id"] for x in p["events"]]))
    leaked = [p["email"] for p in profiles if p["email"] in by_mail]
    res.append(check("profiles.json 에 섞인 테스트 사람", 0, len(leaked)))
    return all(res)


def check_companies(customers, companies, profiles, ksic):
    print("\n■ 회사(Company) · 산업군 확인")
    keys = set(companies["company_key"])
    missing = sorted(set(customers["company_key"].dropna()) - keys)
    mids = set(ksic["mid"])

    def bad_mid(values):
        return [v for v in values if not is_blank(v) and str(v).split(" ", 1)[0] not in mids]

    bad_comp = bad_mid(companies["industry_mid"])
    bad_prof = bad_mid(p["industry_mid"] for p in profiles)
    res = [
        check("Company 기본키 중복", 0, int(companies["company_key"].duplicated().sum())),
        check("Company 에 없는 Customer company_key", 0, len(missing)),
        check("companies.csv industry_mid 중 KSIC 목록 밖 (빈칸 허용)", 0, len(bad_comp)),
        check("profiles.json industry_mid 중 KSIC 목록 밖 (빈칸 허용)", 0, len(bad_prof)),
    ]
    src = companies["industry_source"].fillna("(빈칸)").value_counts().to_dict()
    print(f"  · 회사 {len(companies)}개, industry_source: {src}")
    return all(res)


# ---------------------------------------------------------------- 실행
def save_csv(df, out_dir, name):
    df.to_csv(os.path.join(out_dir, name), index=False, encoding="utf-8-sig")


def save_json(obj, out_dir, name):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)  # NaN 이 섞이면 바로 오류


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-test", action="store_true", help="테스트 명단(E07)을 data/raw/ 에 만듦")
    ap.add_argument("--no-classify", action="store_true",
                    help="LLM(OpenAI) 산업군 분류를 끔 (확정 사전·지난 LLM 결과만 사용)")
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "processed"))
    a = ap.parse_args()
    if a.make_test:
        make_test_file(a.raw_dir)
        return 0
    os.makedirs(a.out_dir, exist_ok=True)

    part, steps_by_file, no_email = load_participation(a.raw_dir)
    events = load_events(a.raw_dir)
    real = part[~part["is_test"]]
    test = part[part["is_test"]]
    surveys = load_surveys(a.raw_dir)
    surveys["matched"] = surveys["email"].isin(set(real["email"].dropna())).map({True: "Y", False: "N"})
    interactions = load_interactions(a.raw_dir, real)
    contents = load_contents(a.raw_dir)
    customers = build_customers(real, events)
    ksic = ci.load_ksic()
    if not ksic:
        print("backend/data/ksic.json 이 없습니다. python backend/data/make_ksic.py 를 먼저 실행해 주세요.")
        return 1
    companies = build_companies(real, customers, ksic, classify=not a.no_classify)

    save_csv(events, a.out_dir, "events.csv")
    save_csv(customers, a.out_dir, "customers.csv")
    save_csv(companies, a.out_dir, "companies.csv")
    save_csv(part, a.out_dir, "participation.csv")
    save_csv(surveys, a.out_dir, "surveys.csv")
    save_csv(interactions, a.out_dir, "interactions.csv")
    save_csv(contents, a.out_dir, "contents.csv")
    save_csv(pd.DataFrame(errors, columns=["file", "row", "column", "reason"]), a.out_dir, "errors.csv")

    print(f"참가자 명단 {len(steps_by_file)}개, 신청 {len(part)}건 읽음 (테스트 {len(test)}건 포함)")
    print(f"오류 목록 {len(errors)}건 → {os.path.relpath(os.path.join(a.out_dir, 'errors.csv'), ROOT)}")
    for e in errors:
        where = f" {e['row']}행" if e["row"] is not None else ""
        col = f" [{e['column']}]" if e["column"] else ""
        print(f"  - {e['file']}{where}{col}: {e['reason']}")

    if no_email:
        for name in ("profiles.json", "profiles_test.json"):  # 예전 결과가 남아 헷갈리지 않도록
            p = os.path.join(a.out_dir, name)
            if os.path.exists(p):
                os.remove(p)
        print("\n" + "!" * 60)
        print("이메일 열을 찾지 못한 파일이 있어 통합 프로필을 만들지 않고 멈춥니다:")
        for f in no_email:
            print(f"  - {f}")
        print("mapping.json 에 이 파일의 이메일 열 이름을 추가한 뒤 다시 실행해 주세요.")
        print("!" * 60)
        return 1

    profiles = build_profiles(real, events, surveys, interactions, companies)
    test_profiles = build_profiles(test, events, surveys.iloc[0:0], interactions.iloc[0:0], companies)
    save_json(profiles, a.out_dir, "profiles.json")
    save_json(test_profiles, a.out_dir, "profiles_test.json")
    print(f"통합 프로필 {len(profiles)}명 → profiles.json, 테스트 프로필 {len(test_profiles)}명 → profiles_test.json")

    ok1 = check_counts(real, customers, surveys, interactions, profiles)
    ok2 = check_test(steps_by_file, test, test_profiles, profiles)
    ok3 = check_companies(customers, companies, profiles, ksic)
    ok = ok1 and ok2 and ok3
    print("\n결과: " + ("모두 OK" if ok else "FAIL 이 있습니다"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
