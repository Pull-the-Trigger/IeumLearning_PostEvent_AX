"""사전 질문 1개 → 갈래 (SALES / ARTICLE / STAFF / FACT / NONE).

1. 질문이 아니면 NONE ("없습니다", ".", 인사) — 규칙, 무료
2. question_map.json 문장과 일치하면 그 갈래 — 무료
3. 그 밖의 표현은 AI가 '뜻'으로 판단 — 19개 질문을 예시로 보여 주고, 기준은 '답의 재료가 어디 있나'
   AI 확신이 낮거나 키가 없으면 STAFF(담당자)
같은 질문은 한 번만 AI에 묻는다 (캐시).
"""
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "question_map.json").read_text(encoding="utf-8"))["rules"]
BRANCHES = ["SALES", "ARTICLE", "STAFF", "FACT", "NONE"]
MIN_CONF = 0.6

NOT_A_QUESTION = re.compile(r"(^없(습니다|어요|음|다)|특별히\s*없|해당\s*없|기대(합니다|하겠습니다|돼요|됩니다)|잘\s*부탁|^감사합니다|^무$|^-$|^n/?a$)", re.I)
QUESTION_MARK = re.compile(r"(\?|나요|까요|ㄹ까|습니까|인가|있나|궁금|알려|되나|하나요|인지)")

SYSTEM = """B2B 기업교육 회사 이음러닝의 행사 참가자가 신청서에 남긴 '사전 질문'을 분류한다.
기준은 '이 질문에 답할 재료가 어디 있는가'이다. 주제가 민감한지는 보지 않는다.
- SALES: 도입 방법, 과정 구성, 비용·견적을 묻거나, 답하려면 상대 회사 정보(규모, 부서, 업종, 현재 수준, 예산, 내부 규정, 인사 제도)를 되물어야 한다.
- ARTICLE: 다른 회사 사례나 일반적인 방법이라, 이음러닝이 발행한 글(사례·가이드)로 답할 수 있다.
- STAFF: 이음러닝의 입장·정책이나 우리가 가진 기록에 없는 정보(강사 이력, 법률 판단 등)가 필요하다. 애매하면 STAFF.
- FACT: 이번 행사 자체의 일정, 장소, 주차, 발표 자료 제공처럼 행사 기록으로 사실만 답하면 된다. 교육 과정의 시간·분량·대상·구성은 행사 정보가 아니라 과정 문의이므로 SALES다.
- NONE: 질문이 아니다 (없음, 인사, 의미 없는 글자).
여러 질문이 섞이면 SALES > STAFF > ARTICLE > FACT 순으로 하나를 고른다.
답을 지어내지 말고 분류만 한다."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["branch", "reason", "confidence"],
          "properties": {"branch": {"type": "string", "enum": BRANCHES},
                         "reason": {"type": "string"},
                         "confidence": {"type": "number"}}}

_cache = {}


def _examples():
    lines = [f"- \"{r.get('example', r['match'])}\" → {r['branch']} ({r['why']})" for r in RULES]
    return "3분기 실제 질문과 정답 예시:\n" + "\n".join(lines)


def classify(question: str, use_llm: bool = True) -> dict:
    q = (question or "").strip()
    if not q:
        return {"branch": "NONE", "reason": "질문 없음", "source": "empty"}
    plain = re.sub(r"[\s.~!·,]+", " ", q).strip()
    if len(plain) <= 2 or (len(plain) <= 25 and NOT_A_QUESTION.search(plain) and not QUESTION_MARK.search(q)):
        return {"branch": "NONE", "reason": "질문이 아닌 글", "source": "rule"}
    for r in RULES:
        # 사전 문장과 거의 같은 길이일 때만 바로 분류. 더 길면 다른 질문이 섞였을 수 있어 AI가 본다
        if r["match"] in q and len(q) <= len(r.get("example", r["match"])) + 8:
            return {"branch": r["branch"], "reason": r["why"], "source": "map"}
    if not use_llm or not os.getenv("OPENAI_API_KEY"):
        return {"branch": "STAFF", "reason": "질문 사전에 없음 → 담당자 (AI 미사용)", "source": "default"}
    if q in _cache:
        return _cache[q]
    from openai import OpenAI, AuthenticationError
    try:
        resp = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            messages=[{"role": "system", "content": SYSTEM + "\n\n" + _examples()},
                      {"role": "user", "content": q}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "pre_question", "strict": True, "schema": SCHEMA}})
    except AuthenticationError:
        k = os.getenv("OPENAI_API_KEY", "")
        raise SystemExit(f"\n[API 키 오류] OpenAI가 키를 거절했어요 (끝 4자리 …{k[-4:]}). "
                         ".env의 키를 다시 복사해 넣었는지, 키가 삭제·만료되지 않았는지 확인하세요.")
    out = json.loads(resp.choices[0].message.content)
    res = {"branch": out["branch"], "reason": "AI: " + out["reason"], "source": "llm",
           "confidence": out["confidence"]}
    if out["confidence"] < MIN_CONF and out["branch"] != "STAFF":
        res = {**res, "branch": "STAFF", "reason": f"AI 확신 낮음({out['confidence']:.2f}, {out['branch']}) → 담당자"}
    _cache[q] = res
    return res
