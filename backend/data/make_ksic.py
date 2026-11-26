"""한국표준산업분류(KSIC) 제11차 엑셀 → backend/data/ksic.json (대분류 21개, 중분류 77개).

실행 (원본 엑셀이 바뀔 때만 한 번):
    python backend/data/make_ksic.py
"""
import json
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 저장소 루트 (backend/data/ 의 두 단계 위)
SRC = os.path.join(ROOT, "data", "ref", "한국표준산업분류_제11차_분류체계.xlsx")
OUT = os.path.join(ROOT, "backend", "data", "ksic.json")
SHEET = "11차개정한국표준산업분류"  # 10차 시트는 무시
SOURCE = ("한국표준산업분류 제11차 개정 (통계청 고시 제2024-2호, 2024-07-01 시행), "
          "통계분류포털 자료실 2024-06-26 게시본 / data/ref/한국표준산업분류_제11차_분류체계.xlsx")
EXPECT_MAJOR, EXPECT_MID = 21, 77


def clean(v):
    if v is None or pd.isna(v):
        return None
    v = str(v).strip()
    return v or None


def main():
    df = pd.read_excel(SRC, sheet_name=SHEET, header=None, skiprows=3, dtype=str)  # 앞 3줄은 제목/헤더
    df = df.map(clean)
    df[0] = df[0].ffill()  # 대분류 코드는 첫 행에만 있음

    major = {}
    for code, name in df.dropna(subset=[1])[[0, 1]].itertuples(index=False):
        major[code] = re.sub(r"\s*\(\d+(~\d+)?\)$", "", name)  # "(10~34)" 같은 범위 제거
    mid = {}
    for major_code, code, name in df.dropna(subset=[2])[[0, 2, 3]].itertuples(index=False):
        mid[code] = {"name": name, "major": major_code}

    if len(major) != EXPECT_MAJOR or len(mid) != EXPECT_MID:
        sys.exit(f"오류: 대분류 {len(major)}개 / 중분류 {len(mid)}개 "
                 f"(기대 {EXPECT_MAJOR} / {EXPECT_MID}). ksic.json 을 만들지 않았습니다.")
    bad = [c for c, m in mid.items() if m["major"] not in major]
    if bad:
        sys.exit(f"오류: 대분류를 찾지 못한 중분류 {bad}. ksic.json 을 만들지 않았습니다.")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "major": major, "mid": mid}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"대분류 {len(major)}개, 중분류 {len(mid)}개 → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
