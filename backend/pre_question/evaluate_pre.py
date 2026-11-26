"""사전 질문 시험지로 '문장 사전만' vs '사전 + AI'를 비교 채점한다.

  python backend/pre_question/evaluate_pre.py data/test/pre_question_tests.json

strict  = 정답(expected)과 같아야 맞음
lenient = 허용 정답(acceptable) 중 하나면 맞음 (경계 사례용)
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[2]
env = ROOT / ".env"
if env.exists():
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")  # .env가 컴퓨터 환경변수보다 우선
from classify import classify  # noqa: E402

items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["items"]
modes = [("문장 사전만", False)]
if os.getenv("OPENAI_API_KEY"):
    modes.append(("사전 + AI", True))
else:
    print("※ OPENAI_API_KEY 없음 → '사전 + AI'는 건너뜀\n")

for name, use_llm in modes:
    strict = lenient = 0
    by_src, wrong = Counter(), []
    for it in items:
        r = classify(it["question"], use_llm=use_llm)
        ok_s, ok_l = r["branch"] == it["expected"], r["branch"] in it["acceptable"]
        strict += ok_s
        lenient += ok_l
        by_src[(it["source"], ok_l)] += 1
        if not ok_l:
            wrong.append(f"  ✗ {it['id']} 정답 {it['expected']} / 결과 {r['branch']} ({r['source']}) — {it['question'][:45]}")
    n = len(items)
    print(f"[{name}] strict {strict}/{n} = {strict / n:.0%} · lenient {lenient}/{n} = {lenient / n:.0%}")
    for s in ["variant", "new", "noise"]:
        t = by_src[(s, True)] + by_src[(s, False)]
        if t:
            print(f"   {s:8s} {by_src[(s, True)]}/{t}")
    print("\n".join(wrong) or "  (틀린 것 없음)")
    print()
