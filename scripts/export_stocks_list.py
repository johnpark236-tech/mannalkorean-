"""
STOCKS_DB 검증용 리스트 출력
- 입력: D:\logofchoices\data\csv\all_stocks.json
- 출력: D:\logofchoices\data\csv\stocks_sector_check.csv  (전체)
        D:\logofchoices\data\csv\stocks_sector_s99.csv    (기타만)
"""
import json
import csv

SECTOR_NAMES = {
    "S01": "반도체·IT",
    "S02": "2차전지·신에너지",
    "S03": "자동차·부품",
    "S04": "조선·방산",
    "S05": "금융·보험",
    "S06": "바이오·헬스",
    "S07": "플랫폼·인터넷",
    "S08": "화학·소재",
    "S09": "건설·부동산",
    "S10": "에너지·자원",
    "S11": "유통·소비재",
    "S12": "통신·인프라",
    "S99": "기타",
}

with open(r"D:\logofchoices\data\csv\all_stocks.json", "r", encoding="utf-8") as f:
    stocks = json.load(f)

# 섹터별 카운트
from collections import Counter
sec_cnt = Counter(s["s"] for s in stocks)
print(f"총 종목 수: {len(stocks):,}개\n")
print(f"{'섹터코드':<6} {'섹터명':<18} {'종목수':>6}")
print("-" * 34)
for code, name in SECTOR_NAMES.items():
    print(f"{code:<6} {name:<18} {sec_cnt.get(code, 0):>6,}")

# 전체 CSV
out_all = r"D:\logofchoices\data\csv\stocks_sector_check.csv"
with open(out_all, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["종목명", "종목코드", "시장", "섹터코드", "섹터명"])
    for s in sorted(stocks, key=lambda x: (x["s"], x["m"], x["n"])):
        w.writerow([s["n"], s["c"], s["m"], s["s"], SECTOR_NAMES.get(s["s"], "기타")])
print(f"\n[전체] {out_all}")

# 기타(S99)만 CSV
out_s99 = r"D:\logofchoices\data\csv\stocks_sector_s99.csv"
s99 = [s for s in stocks if s["s"] == "S99"]
with open(out_s99, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["종목명", "종목코드", "시장"])
    for s in sorted(s99, key=lambda x: (x["m"], x["n"])):
        w.writerow([s["n"], s["c"], s["m"]])
print(f"[기타] {out_s99}  ({len(s99):,}개)")
