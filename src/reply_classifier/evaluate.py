"""테스트 회신(expected 포함)으로 분류 정확도를 잰다.

  python src/reply_classifier/evaluate.py data/test/test_replies.json

FACT 정답 중 '정보 없으면 STAFF'처럼 둘 다 허용되는 경계 사례는 note에 적혀 있고,
여기서는 엄격하게 expected.category와 같은지만 본다.
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_replies import run, ROOT  # noqa: E402

path = sys.argv[1]
gold = {r["reply_id"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))["replies"]}
res = run(path, ROOT / "out" / "eval_results", date(2026, 11, 25))
ok, confusion = 0, Counter()
for r in res:
    exp = gold[r["reply_id"]]["expected"]["category"]
    confusion[(exp, r["category"])] += 1
    if exp == r["category"]:
        ok += 1
    else:
        print(f"✗ {r['reply_id']}: 정답 {exp} / 결과 {r['category']} ({r['source']}) — {gold[r['reply_id']]['body'][:40]}")
print(f"\n정확도 {ok}/{len(res)} = {ok / len(res):.0%}")
print("규칙으로 처리:", sum(r['source'] == 'rule' for r in res), "건")
