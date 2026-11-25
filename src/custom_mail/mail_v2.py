"""맞춤 메일 v2 — 틀(사실·약속) + AI 연결 문장 2~3개.

틀이 넣는 것 (바뀌지 않음): 호칭, 행사명, 담당자 연락 날짜, 글 제목·링크, 서명
AI가 쓰는 것: ① 질문을 자연스럽게 받는 문장 ② 이유 또는 글이 도움 되는 이유 ③ (영업만) 한 줄로 답할 수 있는 선택 질문
AI 재료: 갈래, 직함, 질문 원문, 글 제목·주제 — 이것 말고 사실(숫자·사례·회사명·날짜)은 쓰지 않는다.
사실 검사: AI 문장에 숫자·%·따옴표 인용·금지 표현이 있으면 버리고 틀 문장으로 대신한다.
키가 없으면 전부 틀 문장으로 만든다.
기준 메일: 소민이 쓴 고진혁 전무 메일(11/25)을 다듬은 것
"""
import json
import os
import re

SYSTEM = """너는 B2B 기업교육 회사 이음러닝 마케팅본부장의 메일 문장을 돕는다.
행사 참가자가 신청서에 남긴 사전 질문에 대한 맞춤 메일의 '연결 문장'만 쓴다. 인사, 날짜, 링크, 서명은 쓰지 않는다.

반드시 지킬 것
- 합니다체. 짧고 담백하게. 느낌표·이모지·과장('혁신적', '획기적')·재촉('지금 바로') 금지.
- 질문 원문을 따옴표로 그대로 옮기지 말고 자연스럽게 받는다. 예: "현업이 자동화를 어디까지 직접 만들 수 있을지 궁금해하셨습니다."
- 주어진 재료(질문, 직함, 글 제목·주제) 밖의 사실을 쓰지 않는다. 숫자, 비율, 기간, 다른 회사 사례, 회사 이름, 효과 주장, 이음러닝 서비스 소개를 쓰지 않는다.
- 질문에 대한 답을 지어내지 않는다.

쓸 문장
- ack: 질문을 자연스럽게 받는 한 문장.
- reason:
  · SALES: 왜 회사 상황을 여쭤야 정확히 답할 수 있는지, 무엇을 알아야 하는지 한 문장 (예: 회사가 원하는 목표, 맡은 업무, 지금의 활용 수준).
  · ARTICLE: 주어진 글이 이 질문에 어떻게 도움이 되는지 한 문장. 글 제목·주제에서 알 수 있는 것만.
  · STAFF: 정확한 답을 위해 담당자가 확인한다는 한 문장.
- ask: SALES일 때만. 담당자가 준비해서 연락할 수 있도록, 한 줄로 답할 수 있는 질문 하나를 '혹시 ~가 있으시면 회신으로 한 줄만 남겨 주십시오.' 형태로. 다른 갈래는 빈 문자열.
- subject_topic: 질문의 핵심을 10자 안팎 명사구로 (예: 현업 자동화 수준).

기준 메일 (SALES, 이런 느낌으로)
현업이 자동화를 어디까지 직접 만들 수 있을지 궁금해하셨습니다. 이 부분은 회사가 원하는 목표, 현업이 맡은 업무, 지금의 활용 수준에 따라 답이 크게 달라져서 회사 상황을 여쭙고 말씀드리는 것이 정확합니다. 혹시 먼저 생각하고 계신 업무가 있으시면 회신으로 한 줄만 남겨 주십시오."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["ack", "reason", "ask", "subject_topic"],
          "properties": {k: {"type": "string"} for k in ["ack", "reason", "ask", "subject_topic"]}}

BAD = re.compile(r"(\d|%|퍼센트|‘|’|\"|“|”|!|혁신|획기|압도|지금 바로|놓치지|이음 진단|이음 캠프|이음 패스|사례에서|저희 고객)")
_cache = {}


def _strip(q):
    return q.strip().rstrip(".?!。 ")


def fallback(branch, q, art, label):
    ack = f"‘{_strip(q)}’라는 질문을 남겨 주셨습니다." if q else ""
    reason = {"SALES": "이 부분은 회사가 원하는 목표와 지금의 상황에 따라 답이 달라져서, 회사 상황을 여쭙고 말씀드리는 것이 정확합니다.",
              "ARTICLE": "이 질문과 관련된 내용을 정리한 글을 전해 드립니다.",
              "STAFF": "정확한 답변을 드리기 위해 담당자가 확인한 뒤 따로 답변드리겠습니다.",
              "FACT": "", "CUSTOM_TOPIC": ""}.get(branch, "")
    ask = "혹시 먼저 이야기 나누고 싶은 부분이 있으시면 회신으로 한 줄만 남겨 주십시오." if branch == "SALES" else ""
    return {"ack": ack, "reason": reason, "ask": ask, "subject_topic": label or "남겨 주신 질문", "source": "template"}


def lines_for(branch, title, q, art, label):
    """AI 연결 문장. 실패·키 없음·검사 탈락이면 틀 문장."""
    fb = fallback(branch, q, art, label)
    if not q or branch not in ("SALES", "ARTICLE", "STAFF") or not os.getenv("OPENAI_API_KEY"):
        return fb
    key = (branch, title_group(title), q, art["content_id"] if art else "")
    if key in _cache:
        return _cache[key]
    from openai import OpenAI
    user = (f"갈래: {branch}\n직함: {title}\n질문: {q}\n"
            f"글: {(art['title'] + ' (주제: ' + art['topic'] + ')') if art else '없음'}")
    try:
        resp = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "mail_lines", "strict": True, "schema": SCHEMA}})
        out = json.loads(resp.choices[0].message.content)
    except Exception as e:  # 네트워크·키 문제면 틀 문장으로
        res = {**fb, "source": f"template (AI 실패: {type(e).__name__})"}
        _cache[key] = res
        return res
    if branch != "SALES":
        out["ask"] = ""
    bad = [k for k in ("ack", "reason", "ask") if out[k] and BAD.search(out[k])]
    for k in bad:  # 검사에 걸린 문장만 틀 문장으로 바꾼다
        out[k] = fb[k]
    if not out["subject_topic"] or BAD.search(out["subject_topic"]) or len(out["subject_topic"]) > 20:
        out["subject_topic"] = fb["subject_topic"]
    res = {**out, "source": "ai" + (f" (틀로 교체: {', '.join(bad)})" if bad else "")}
    _cache[key] = res
    return res


def _iga(word):
    ch = word.strip()[-1]
    return "이" if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else "가"


def title_group(title):
    """같은 질문이라도 직함군이 다르면 문장을 따로 만든다 (경영진에게는 더 짧게 등)."""
    if any(k in title for k in ("대표", "CEO", "전무", "부사장", "상무", "본부장", "실장", "이사", "공장장", "CTO")):
        return "경영진"
    return "실무"


def render_v2(row, art, prev_event, due, label, same_company_n, rep=None, survey_line=""):
    title = row.get("title") or ""
    name = f"{row['name']} {title}님" if title else f"{row['name']} 담당자님"
    q, ev, br = row["pre_question"], row["event_name"], row["branch"]
    L = lines_for(br, title, q, art, label)
    parts = [f"{name}, 안녕하세요. 이음러닝 마케팅본부장 한서윤입니다."]
    why = {"SALES": f"{ev}에 남겨 주신 질문과 관련해 연락드립니다." if q else f"{ev}에 남겨 주신 내용과 관련해 연락드립니다.",
           "ARTICLE": f"{ev}에 남겨 주신 질문에 답변드리고자 연락드립니다.",
           "STAFF": f"{ev}에 남겨 주신 질문과 관련해 연락드립니다.",
           "FACT": f"{ev}에 남겨 주신 질문에 답변드리고자 연락드립니다.",
           "CUSTOM_TOPIC": f"{ev} 설문에 남겨 주신 관심 주제와 관련해 연락드립니다."}[br]
    parts.append(" ".join(x for x in [why, f"지난 {prev_event}에 이어 다시 참석해 주셔서 감사합니다." if prev_event else "",
                                      survey_line] if x))
    if br == "SALES":
        if q:
            parts.append(" ".join(x for x in [L["ack"], L["reason"]] if x))
        elif "설문 연락 희망" in row["sales_triggers"]:
            parts.append("설문에서 담당자 연락을 요청해 주셨습니다.")
        else:
            parts.append("남겨 주신 내용을 바탕으로 필요하신 부분을 여쭙고자 합니다.")
        who = f"{rep['team']} {rep['name']} {rep['position']}{_iga(rep['position'])}" if rep else "담당자가"
        promise = f"{who} {due.month}월 {due.day}일까지 연락드리겠습니다."
        if not q:
            promise += " 혹시 먼저 이야기 나누고 싶은 부분이 있으시면 회신으로 한 줄만 남겨 주십시오. 그 내용을 기준으로 준비해서 연락드리겠습니다."
        if q:
            promise += " " + L["ask"].replace("회신으로 한 줄만 남겨 주십시오.", "회신으로 한 줄만 남겨 주십시오. 그 내용을 기준으로 준비해서 연락드리겠습니다.")
        parts.append(promise)
        if art:
            parts.append(f"그 전에 참고하실 수 있도록 관련 글을 한 편 전해 드립니다.\n「{art['title']}」\n{art['url']}")
    elif br == "ARTICLE":
        parts.append(" ".join(x for x in [L["ack"], L["reason"]] if x) + f"\n「{art['title']}」\n{art['url']}")
    elif br == "STAFF":
        # 약속 문장은 틀로 고정 ("따로 답변드리겠습니다"가 빠지지 않게)
        who = f"{rep['team']} {rep['name']} {rep['position']}{_iga(rep['position'])}" if rep else "담당자가"
        parts.append(" ".join(x for x in [L["ack"], f"정확한 답변을 드리기 위해 {who} 확인한 뒤 따로 답변드리겠습니다."] if x))
        if art:
            parts.append(f"직접적인 답은 아니지만 참고가 될 만한 글을 먼저 전해 드립니다.\n「{art['title']}」\n{art['url']}")
    elif br == "FACT":
        parts.append(f"{L['ack']} [행사 기록으로 답변 작성 — 기록에 없으면 담당자 확인]")
    elif br == "CUSTOM_TOPIC":
        parts.append(f"설문에서 ‘{row['survey_topic']}’에 관한 이야기를 듣고 싶다고 남겨 주셔서, 이 주제를 다룬 글을 전해 드립니다.\n"
                     f"「{art['title']}」\n{art['url']}")
    if br != "SALES":
        parts.append("궁금하신 점은 이 메일로 회신해 주십시오.")
    parts.append("이음러닝 마케팅본부장 한서윤 드림")
    topic = (label or L["subject_topic"]) if q else ("담당자 연락 요청" if br == "SALES" else row.get("survey_topic") or "관심 주제")
    subject = f"[이음러닝] {ev}에 남겨 주신 ‘{topic}’ 관련" + (" 글" if br in ("ARTICLE", "CUSTOM_TOPIC") else "")
    note = f"같은 회사 수신자 {same_company_n}명 — 문장이 겹치지 않는지 확인" if same_company_n > 1 else ""
    return subject, "\n\n".join(parts), L["source"], note
