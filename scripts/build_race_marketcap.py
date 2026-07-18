"""
build_race_marketcap.py
data/stocks/*.json 의 mc(시가총액) 필드를 분기말 기준으로 집계
→ data/race/stock_marketcap.json
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
from pathlib import Path
from datetime import date

STOCKS_DIR = Path(__file__).parent.parent / "data" / "stocks"
RACE_DIR   = Path(__file__).parent.parent / "data" / "race"
OUT_FILE   = RACE_DIR / "stock_marketcap.json"

# 분기말 기준일 (월 → Q 마지막 달)
QUARTER_END_MONTHS = {3, 6, 9, 12}

def quarter_label(d_str: str) -> str:
    """'20240930' → '2024Q3'"""
    y = d_str[:4]
    m = int(d_str[4:6])
    q = (m - 1) // 3 + 1
    return f"{y}Q{q}"

def is_quarter_end(d_str: str) -> bool:
    """날짜 문자열이 분기말 달(3·6·9·12월)인지 확인."""
    m = int(d_str[4:6])
    return m in QUARTER_END_MONTHS

def main():
    RACE_DIR.mkdir(parents=True, exist_ok=True)

    # ── 전체 종목 JSON 로드 ──────────────────────────────────────────
    stocks = []
    for path in sorted(STOCKS_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        with open(path, encoding="utf-8") as f:
            stocks.append(json.load(f))
    print(f"종목 {len(stocks)}개 로드")

    # ── 분기별 마지막 거래일의 mc 추출 ─────────────────────────────
    # structure: { quarter_key: { code: (name, mc_value_trillion) } }
    quarterly: dict[str, dict[str, tuple]] = {}

    for doc in stocks:
        code = doc["id"]
        name = doc["name"]
        series = doc.get("series", [])

        # 분기별 마지막 mc 찾기
        q_last: dict[str, dict] = {}  # {qkey: last_record_with_mc}
        for r in series:
            if "mc" not in r or not r["mc"]:
                continue
            m = int(r["d"][4:6])
            if m not in QUARTER_END_MONTHS:
                continue
            q = quarter_label(r["d"])
            # 같은 분기 내 날짜 오름차순이므로 나중에 올수록 최신
            if q not in q_last or r["d"] >= q_last[q]["d"]:
                q_last[q] = r

        for q, r in q_last.items():
            if q not in quarterly:
                quarterly[q] = {}
            mc_tril = round(r["mc"] / 1_000_000_000_000, 1)
            quarterly[q][code] = (name, mc_tril)

    if not quarterly:
        print("[X] mc 데이터 없음 — 금융위 API 수집 후 재시도")
        return

    # ── 타임라인 생성 ─────────────────────────────────────────────────
    # 분기당 최소 3개 종목 조건, 날짜 오름차순
    timeline = []
    for q in sorted(quarterly.keys()):
        entries = quarterly[q]
        if len(entries) < 3:
            continue
        items = sorted(
            [{"name": name, "value": val, "code": code} for code, (name, val) in entries.items()],
            key=lambda x: -x["value"]
        )
        # 분기 → 날짜 추정 (Q1→0331, Q2→0630, Q3→0930, Q4→1231)
        y, qn = q[:4], int(q[5])
        ends = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}
        d_str = y + ends[qn]
        timeline.append({"date": d_str, "items": items})

    print(f"타임라인: {len(timeline)}포인트  ({timeline[0]['date']} ~ {timeline[-1]['date']})")

    # ── 마지막 프레임 상위 5 출력 ─────────────────────────────────────
    last = timeline[-1]
    print(f"\n최신 프레임 ({last['date']}) 상위 5:")
    for item in last["items"][:5]:
        print(f"  {item['name']:15} {item['value']:,.1f}조원")

    # ── 저장 ──────────────────────────────────────────────────────────
    out = {
        "id":       "stock_marketcap",
        "title":    "국내 주식 시가총액 순위",
        "mode":     "ranking",
        "type":     "race_chart",
        "unit":     "조원",
        "updated":  date.today().strftime("%Y-%m-%d"),
        "source":   "금융위원회_주식시세정보",
        "timeline": timeline,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    kb = OUT_FILE.stat().st_size / 1024
    print(f"\n[OK] {OUT_FILE.name}  {kb:.1f}KB")

if __name__ == "__main__":
    main()
