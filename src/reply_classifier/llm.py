"""규칙으로 판단이 안 된 회신만 OpenAI Structured Outputs로 분류한다.

OPENAI_API_KEY가 없으면 호출하지 않고 None을 돌려준다 → 담당자 확인으로 넘어간다.
키는 레포 루트의 .env에 넣는다 (.gitignore에 포함됨, 절대 커밋하지 말 것).
"""
import json
import os

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
CATEGORIES = ["SALES", "MATERIAL", "FACT", "STAFF", "UNSUBSCRIBE", "AUTO_REPLY", "THANKS_ONLY"]

SYSTEM = """너는 B2B 기업교육 회사 이음러닝의 행사 후속 메일 회신을 분류한다.
기준은 '답의 재료가 어디에 있는가'이다. 주제가 민감한지는 보지 않는다.
아래 순서로 판단하고, 먼저 해당하는 분류 하나만 고른다.
1. AUTO_REPLY: 부재중·휴가 자동 응답
2. UNSUBSCRIBE: 메일을 그만 받고 싶다는 의사
3. SALES: 견적, 미팅, 제안, 비용, 도입 상담·절차, 과정 구성 요청.
   또는 답하려면 상대 회사 정보(규모, 부서, 업종, 현재 수준, 예산, 내부 규정·인사 제도)를 되물어야 하는 질문.
4. MATERIAL: 발표 자료, 회사 소개서 요청
5. FACT: 이음러닝이 가진 기록(행사 일정·장소, 설문·자료 링크, 발행한 글)만으로 정확히 답할 수 있는 질문
6. STAFF: 3~5 어디에도 재료가 없어 이음러닝이 새로 정하거나 알아봐야 하는 질문, 또는 의도가 애매한 경우
7. THANKS_ONLY: 질문 없이 감사 인사만
애매하면 STAFF를 고른다. 답을 지어내지 않는다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "reason": {"type": "string", "description": "한 문장 근거, 회신 본문 표현을 인용"},
        "confidence": {"type": "number"},
    },
    "required": ["category", "reason", "confidence"],
    "additionalProperties": False,
}


def classify_by_llm(subject: str, body: str, profile_summary: str):
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI  # pip install openai
    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"[보낸 사람]\n{profile_summary}\n\n[제목]\n{subject}\n\n[본문]\n{body}"},
        ],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "reply_class", "strict": True, "schema": SCHEMA}},
    )
    out = json.loads(resp.choices[0].message.content)
    return {"category": out["category"], "reasons": [f"AI: {out['reason']}"],
            "confidence": float(out["confidence"]), "needs_human": out["category"] == "STAFF",
            "source": "llm"}
