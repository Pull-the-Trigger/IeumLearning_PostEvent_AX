"""회신 메일 1차 분류 규칙.

규칙은 특정 데이터가 아니라 고객 인터뷰 기준(9·10번)에서 나온 표현으로만 만든다.
새 행사·새 명단이 들어와도 그대로 쓸 수 있도록, 사람·회사·행사 이름은 넣지 않는다.

분류 순서 (먼저 걸리는 것이 이긴다):
  1. AUTO_REPLY   부재중 자동 응답
  2. UNSUBSCRIBE  수신 거부 의사
  3. SALES        견적·미팅·제안·비용·도입 절차, 또는 답하려면 상대 회사 정보가 필요한 질문
                  (사내 자료 기준·인사 평가 연계 포함 — 11/25 팀 결정)
  4. MATERIAL     발표 자료·소개서 요청
  5. STAFF        우리 기록에 답이 없음 (이음러닝 입장·확인서·개인정보 문의·약속 누락 등)
  6. FACT         일정·장소·링크 같은 사실 문의
  7. THANKS_ONLY  질문 없이 인사만
  8. 그 밖        AMBIGUOUS → AI 판단(키가 있을 때) 또는 담당자
"""
import re

AUTO_REPLY_SUBJECT = re.compile(r"(자동\s*회신|자동\s*응답|부재\s*중|automatic reply|auto[- ]?reply|out of (the )?office)", re.I)
AUTO_REPLY_BODY = re.compile(r"(부재\s*중|휴가로|출장으로|메일 확인이 어렵|복귀 후|out of (the )?office|limited access to email)", re.I)

UNSUBSCRIBE = re.compile(r"(수신\s*(을\s*)?거부|그만\s*받|보내지\s*말|받고\s*싶지\s*않|구독\s*(을\s*)?(해지|취소)|메일\s*(을\s*)?중단|unsubscribe)", re.I)

SALES = re.compile(r"(견적|요금|단가|수강료|얼마|미팅|회의\s*가능|상담|제안서|제안\s*요청|비용|가격|금액|예산|도입[^\n.]{0,12}(검토|고민|진행|절차|과정|문의)|진행\s*절차|과정\s*(구성|설계)|맞춤형으로|계약|발주|교육\s*(을|를)?\s*검토|사내\s*(고객\s*)?(자료|데이터)|인사\s*평가)")
MATERIAL = re.compile(r"(소개서|발표\s*자료|강의\s*자료|자료[^\n.?]{0,8}(받|보내|공유|부탁)|링크가\s*(열리지|안\s*열|작동)|다시\s*보내|원문)")
STAFF = re.compile(r"(기준|규정|허용|정책|개인정보|메일\s*주소는\s*어떻게|수신\s*동의를\s*한\s*기억|확인서|이수증|수료증|입장이\s*궁금|보내주신다고\s*하셨|아직\s*못\s*받)")
FACT = re.compile(r"(일정|언제|장소|어디서|위치|링크|녹화|다시\s*보기|설문)")
QUESTION = re.compile(r"(\?|나요|까요|ㄹ까요|습니까|인가요|있나요|궁금)")
THANKS = re.compile(r"(감사|고맙|잘\s*봤|잘\s*읽)")

# 부분 해지("정기 메일만 그만, 행사 소식은 받고 싶다")는 사람이 확인한다
PARTIAL_UNSUB = re.compile(r"(만\s*받고\s*싶|소식은\s*받|빈도)")


def classify_by_rules(subject: str, body: str) -> dict:
    """규칙으로 분류한다. 확신할 수 없으면 category='AMBIGUOUS'."""
    text = f"{subject}\n{body}"
    hits = []

    if AUTO_REPLY_SUBJECT.search(subject or "") or AUTO_REPLY_BODY.search(body or ""):
        return _r("AUTO_REPLY", ["자동 응답 표현"], 0.95)

    if UNSUBSCRIBE.search(body or ""):
        if PARTIAL_UNSUB.search(body or ""):
            return _r("UNSUBSCRIBE", ["수신 거부(부분 해지 가능성)"], 0.6, needs_human=True)
        return _r("UNSUBSCRIBE", ["수신 거부 표현"], 0.9)

    m = SALES.search(text)
    if m:
        hits.append(f"영업 표현: {m.group(0)}")
        if MATERIAL.search(text):
            hits.append("자료·소개서 요청도 함께 있음 → 바로 발송 후 기록")
        return _r("SALES", hits, 0.85)

    m = MATERIAL.search(text)
    if m:
        return _r("MATERIAL", [f"자료 요청 표현: {m.group(0)}"], 0.8)

    m = STAFF.search(text)
    if m:
        return _r("STAFF", [f"정책·민감 표현: {m.group(0)}"], 0.8)

    m = FACT.search(text)
    if m and QUESTION.search(text):
        return _r("FACT", [f"사실 문의 표현: {m.group(0)}"], 0.7)

    # 인사만 있는 짧은 회신만 종료한다. 제목의 "감사합니다"(우리가 보낸 메일 제목)는 보지 않는다.
    b = (body or "").strip()
    if THANKS.search(b) and not QUESTION.search(b) and len(b) <= 40:
        return _r("THANKS_ONLY", ["질문 없는 짧은 감사 인사"], 0.75)

    return _r("AMBIGUOUS", ["규칙으로 판단 불가"], 0.0, needs_human=True)


def _r(category, reasons, confidence, needs_human=False):
    return {"category": category, "reasons": reasons, "confidence": confidence,
            "needs_human": needs_human, "source": "rule"}
