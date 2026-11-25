"""회사 → KSIC 중분류 분류 (내부용: 영업 전달 카드, 성과 분석, 고객군 제안. 고객 메일 문장에는 쓰지 않음).

분류 순서
  1. src/industry_manual.json 사람이 수정한 값 {company_key: 중분류 코드} → source=manual (LLM 안 부름, 2보다 우선)
  2. src/industry_llm.json    지난 LLM 결과 {company_key: 중분류 코드 또는 ""} → source=llm
  3. 둘 다 없으면 빈칸. 기본 실행에서 OPENAI_API_KEY 가 있으면 1·2 어디에도 없는 회사만 LLM(OpenAI)에 물어 2에 추가
     (--no-classify 로 끌 수 있음)
틀린 값은 src/industry_manual.json 에 직접 고쳐 넣으면 다음 실행부터 반영됩니다.
대분류는 LLM에 묻지 않고 ksic.json 에서 중분류로 찾습니다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KSIC_PATH = os.path.join(ROOT, "src", "ksic.json")
MANUAL_PATH = os.path.join(ROOT, "src", "industry_manual.json")
LLM_PATH = os.path.join(ROOT, "src", "industry_llm.json")
ENV_PATH = os.path.join(ROOT, ".env")
DEFAULT_MODEL = "gpt-4.1-mini"  # 단순 분류라 가벼운 모델. .env 의 OPENAI_MODEL 로 바꿀 수 있음
BATCH_SIZE = 50


def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_ksic():
    return _load_json(KSIC_PATH)


def load_manual():
    return _load_json(MANUAL_PATH)


def load_llm():
    return _load_json(LLM_PATH)


def save_llm(results):
    with open(LLM_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(results.items())), f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_env(name):
    """환경변수 → .env 순서로 찾음. 없으면 None."""
    if os.environ.get(name):
        return os.environ[name]
    if not os.path.exists(ENV_PATH):
        return None
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == name:
                return v.strip().strip("'\"") or None
    return None


def _warn(msg):
    print(f"  [경고] {msg}")


def _prompt(ksic):
    codes = "\n".join(f"{c} {m['name']}" for c, m in ksic["mid"].items())
    return (
        "너는 한국 회사를 한국표준산업분류(KSIC) 제11차 중분류로 분류한다.\n"
        "각 회사의 회사명과 이메일 도메인을 보고, 아래 목록에서 주된 사업에 해당하는 중분류 코드 하나만 고른다.\n"
        "- 사업이 여러 개면 주된 사업 하나만.\n"
        "- 확신이 없으면 mid 를 빈 문자열 \"\" 로 둔다. 추측하지 않는다.\n"
        "- 도메인은 개인 메일(gmail.com 등)일 수 있으니 그때는 회사명만 본다.\n"
        "- 입력의 company_key 를 그대로 돌려준다.\n\n"
        f"중분류 목록:\n{codes}"
    )


def _schema(ksic):
    return {
        "name": "ksic_mid",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company_key": {"type": "string"},
                            "mid": {"type": "string"},
                        },
                        "required": ["company_key", "mid"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": False,
        },
    }


def classify(companies, ksic):
    """companies: [{"company_key", "company_name", "domain"}] → {company_key: 코드 또는 ""}.

    키·패키지가 없거나 API 오류가 나면 경고만 남기고 해당 회사는 결과에서 빠집니다(빈칸).
    """
    if not companies:
        return {}
    key = read_env("OPENAI_API_KEY")
    if not key:
        _warn("OPENAI_API_KEY 가 없어 산업군 LLM 분류를 건너뜁니다 (.env 확인). 미분류 회사는 빈칸으로 둡니다.")
        return {}
    try:
        from openai import OpenAI
    except ImportError:
        _warn("openai 패키지가 없어 산업군 LLM 분류를 건너뜁니다 (pip install openai). 미분류 회사는 빈칸으로 둡니다.")
        return {}
    model = read_env("OPENAI_MODEL") or DEFAULT_MODEL
    client = OpenAI(api_key=key)
    system, schema = _prompt(ksic), _schema(ksic)
    wanted = {c["company_key"] for c in companies}
    out = {}
    for i in range(0, len(companies), BATCH_SIZE):
        batch = companies[i:i + BATCH_SIZE]
        items = [{"company_key": c["company_key"], "company_name": c["company_name"], "domain": c["domain"]}
                 for c in batch]
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": json.dumps(items, ensure_ascii=False)}],
                response_format={"type": "json_schema", "json_schema": schema},
            )
            data = json.loads(resp.choices[0].message.content)
        except Exception as e:  # 네트워크·API·JSON 오류 모두 이 묶음만 빈칸
            _warn(f"LLM 분류 {i + 1}~{i + len(batch)}번째 회사 실패 ({type(e).__name__}: {e}). 빈칸으로 둡니다.")
            continue
        for r in data.get("results", []):
            if r.get("company_key") in wanted:
                out[r["company_key"]] = str(r.get("mid") or "").strip()
    print(f"  LLM({model}) 산업군 분류: 요청 {len(companies)}개 / 응답 {len(out)}개")
    return out


def label_mid(code, ksic):
    return f"{code} {ksic['mid'][code]['name']}"


def label_major(code, ksic):
    major = ksic["mid"][code]["major"]
    return f"{major} {ksic['major'][major]}"


def resolve(company_keys, manual, llm, ksic, err):
    """{company_key: (industry_major, industry_mid, industry_source)}. 목록 밖 코드는 err(...) 후 빈칸."""
    out = {}
    for k in company_keys:
        if k in manual:
            code, source, where = manual[k], "manual", "src/industry_manual.json"
        elif k in llm:
            code, source, where = llm[k], "llm", "LLM"
        else:
            out[k] = (None, None, None)
            continue
        code = str(code or "").strip()
        if not code:
            # manual 의 "" = 사람이 확인했지만 미분류 / llm 의 "" = 확신 없음
            out[k] = (None, None, source if source == "manual" else None)
            continue
        if code not in ksic["mid"]:
            err("classify_industry", f"KSIC 중분류 목록에 없는 코드 '{code}' ({where})", column=k)
            out[k] = (None, None, None)
            continue
        out[k] = (label_major(code, ksic), label_mid(code, ksic), source)
    return out
