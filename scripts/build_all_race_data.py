"""
build_all_race_data.py
data/stocks/*.json 로부터 순위 레이스용 JSON 전체 생성

생성 파일:
  data/race/stock_marketcap.json   (기존 동일 로직)
  data/race/sector_marketcap.json  섹터별 시가총액 합산
  data/race/stock_return_ytd.json  종목별 연간 수익률
  data/race/stock_return_3y.json   종목별 3년 누적 수익률 (분기)
  data/race/stock_volume.json      분기 평균 일 거래량 (만주)
  data/race/stock_tradevalue.json  분기 평균 일 거래대금 (억원)
  data/race/sector_semi.json       반도체·전자 섹터 내 시총
  data/race/sector_battery.json    배터리·에너지 섹터 내 시총
  data/race/sector_bio.json        바이오·헬스케어 섹터 내 시총
  data/race/sector_auto.json       자동차·모빌리티 섹터 내 시총
  data/race/sector_finance.json    금융·보험 섹터 내 시총
  data/race/sector_internet.json   인터넷·플랫폼 섹터 내 시총
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
from pathlib import Path
from datetime import date

STOCKS_DIR = Path(__file__).parent.parent / "data" / "stocks"
RACE_DIR   = Path(__file__).parent.parent / "data" / "race"

# ── 섹터 분류 ──────────────────────────────────────────────────────────────
SECTOR_MAP = {
    "005930": "반도체·전자",   # 삼성전자
    "000660": "반도체·전자",   # SK하이닉스
    "066570": "반도체·전자",   # LG전자
    "373220": "배터리·에너지", # LG에너지솔루션
    "006400": "배터리·에너지", # 삼성SDI
    "051910": "배터리·에너지", # LG화학
    "003670": "배터리·에너지", # 포스코퓨처엠
    "207940": "바이오·헬스케어", # 삼성바이오로직스
    "068270": "바이오·헬스케어", # 셀트리온
    "005380": "자동차·모빌리티", # 현대차
    "000270": "자동차·모빌리티", # 기아
    "012330": "자동차·모빌리티", # 현대모비스
    "105560": "금융·보험",    # KB금융
    "055550": "금융·보험",    # 신한지주
    "035420": "인터넷·플랫폼", # NAVER
    "035720": "인터넷·플랫폼", # 카카오
    "005490": "철강·소재",    # POSCO홀딩스
    "028260": "기타",          # 삼성물산
    "015760": "에너지·공공",   # 한국전력
    "017670": "통신",          # SK텔레콤
}

# 섹터 전용 레이스 대상 종목
SECTOR_RACES = {
    "sector_semi":     ["005930","000660","066570"],
    "sector_battery":  ["373220","006400","051910","003670"],
    "sector_bio":      ["207940","068270"],
    "sector_auto":     ["005380","000270","012330"],
    "sector_finance":  ["105560","055550"],
    "sector_internet": ["035420","035720"],
}

QUARTER_END_MONTHS = {3,6,9,12}

def quarter_label(d_str):
    y, m = d_str[:4], int(d_str[4:6])
    return f"{y}Q{(m-1)//3+1}"

def quarter_end_str(qkey):
    y, qn = qkey[:4], int(qkey[5])
    return y + {1:"0331",2:"0630",3:"0930",4:"1231"}[qn]

def load_stocks():
    stocks = []
    for p in sorted(STOCKS_DIR.glob("*.json")):
        if p.name == "index.json": continue
        stocks.append(json.load(open(p, encoding="utf-8")))
    return stocks

def last_qend_record(series, qkey):
    """분기 내 mc가 있는 마지막 레코드"""
    best = None
    for r in series:
        m = int(r["d"][4:6])
        if m not in QUARTER_END_MONTHS: continue
        if quarter_label(r["d"]) != qkey: continue
        if "mc" not in r or not r["mc"]: continue
        if best is None or r["d"] >= best["d"]:
            best = r
    return best

def save(obj, fname):
    path = RACE_DIR / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {fname}  {path.stat().st_size/1024:.1f}KB")

# ══════════════════════════════════════════════════════════════════════════════
# 1. 시가총액 레이스 (단일 종목 / 섹터 필터 공용)
# ══════════════════════════════════════════════════════════════════════════════
def build_marketcap(stocks, codes_filter=None, fname="stock_marketcap.json",
                    title="국내 주식 시가총액 순위", unit="조원"):
    quarterly = {}
    for doc in stocks:
        code = doc["id"]
        if codes_filter and code not in codes_filter: continue
        name = doc["name"]
        quarters_seen = {}
        for r in doc.get("series", []):
            if "mc" not in r or not r["mc"]: continue
            m = int(r["d"][4:6])
            if m not in QUARTER_END_MONTHS: continue
            q = quarter_label(r["d"])
            if q not in quarters_seen or r["d"] >= quarters_seen[q]["d"]:
                quarters_seen[q] = r
        for q, r in quarters_seen.items():
            quarterly.setdefault(q, {})[code] = (name, round(r["mc"]/1e12, 1))

    timeline = []
    for q in sorted(quarterly):
        entries = quarterly[q]
        if len(entries) < 2: continue
        items = sorted(
            [{"name":n,"value":v,"code":c} for c,(n,v) in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": quarter_end_str(q), "items": items})

    if not timeline: return print(f"  [SKIP] {fname}: 데이터 없음")
    out = {"id": fname.replace(".json",""), "title": title, "mode":"ranking",
           "type":"race_chart", "unit": unit,
           "updated": date.today().isoformat(), "source":"금융위원회_주식시세정보",
           "timeline": timeline}
    save(out, fname)

# ══════════════════════════════════════════════════════════════════════════════
# 2. 섹터별 시가총액 합산
# ══════════════════════════════════════════════════════════════════════════════
def build_sector_marketcap(stocks):
    quarterly = {}
    for doc in stocks:
        code = doc["id"]
        sector = SECTOR_MAP.get(code, "기타")
        for r in doc.get("series", []):
            if "mc" not in r or not r["mc"]: continue
            m = int(r["d"][4:6])
            if m not in QUARTER_END_MONTHS: continue
            q = quarter_label(r["d"])
            bucket = quarterly.setdefault(q, {})
            if code not in bucket or r["d"] >= bucket[code][2]:
                bucket[code] = (sector, r["mc"], r["d"])

    # 섹터별 합산
    sector_q = {}
    for q, codes in quarterly.items():
        for code, (sector, mc, _) in codes.items():
            sector_q.setdefault(q, {}).setdefault(sector, 0)
            sector_q[q][sector] += mc

    timeline = []
    for q in sorted(sector_q):
        entries = sector_q[q]
        if len(entries) < 2: continue
        items = sorted(
            [{"name":s,"value":round(v/1e12,1),"code":s} for s,v in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": quarter_end_str(q), "items": items})

    out = {"id":"sector_marketcap","title":"섹터별 시가총액 순위","mode":"ranking",
           "type":"race_chart","unit":"조원",
           "updated":date.today().isoformat(),"source":"금융위원회_주식시세정보",
           "timeline":timeline}
    save(out, "sector_marketcap.json")

# ══════════════════════════════════════════════════════════════════════════════
# 3. 연간 수익률 (YTD)
# ══════════════════════════════════════════════════════════════════════════════
def build_return_ytd(stocks):
    yearly = {}
    for doc in stocks:
        code, name = doc["id"], doc["name"]
        by_year = {}
        for r in doc.get("series", []):
            if "c" not in r: continue
            y = r["d"][:4]
            by_year.setdefault(y, []).append(r)
        for y, recs in by_year.items():
            recs_s = sorted(recs, key=lambda x:x["d"])
            if len(recs_s) < 20: continue  # 거래일 20일 미만 연도 제외
            first_c = recs_s[0]["c"]
            last_c  = recs_s[-1]["c"]
            if not first_c: continue
            ret = round((last_c / first_c - 1) * 100, 1)
            yearly.setdefault(y, {})[code] = (name, ret)

    timeline = []
    for y in sorted(yearly):
        entries = yearly[y]
        if len(entries) < 3: continue
        items = sorted(
            [{"name":n,"value":v,"code":c} for c,(n,v) in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": y+"1231", "items": items})

    out = {"id":"stock_return_ytd","title":"종목별 연간 수익률 순위","mode":"ranking",
           "type":"race_chart","unit":"%",
           "updated":date.today().isoformat(),"source":"FinanceDataReader+금융위원회",
           "timeline":timeline}
    save(out, "stock_return_ytd.json")

# ══════════════════════════════════════════════════════════════════════════════
# 4. 3년 누적 수익률 (분기 기준)
# ══════════════════════════════════════════════════════════════════════════════
def build_return_3y(stocks):
    # 종목별 분기말 종가 수집
    stock_qprice = {}
    for doc in stocks:
        code, name = doc["id"], doc["name"]
        qmap = {}
        for r in doc.get("series", []):
            if "c" not in r: continue
            m = int(r["d"][4:6])
            if m not in QUARTER_END_MONTHS: continue
            q = quarter_label(r["d"])
            if q not in qmap or r["d"] >= qmap[q][0]:
                qmap[q] = (r["d"], r["c"])
        stock_qprice[code] = {"name": name, "qmap": qmap}

    all_quarters = sorted({q for v in stock_qprice.values() for q in v["qmap"]})

    timeline = []
    for i, q_now in enumerate(all_quarters):
        # 3년 전 분기
        y_now, qn_now = int(q_now[:4]), int(q_now[5])
        y_3y = y_now - 3
        q_3y = f"{y_3y}Q{qn_now}"
        entries = {}
        for code, info in stock_qprice.items():
            qmap = info["qmap"]
            if q_now not in qmap or q_3y not in qmap: continue
            p_now = qmap[q_now][1]
            p_3y  = qmap[q_3y][1]
            if not p_3y: continue
            ret = round((p_now / p_3y - 1) * 100, 1)
            entries[code] = (info["name"], ret)
        if len(entries) < 3: continue
        items = sorted(
            [{"name":n,"value":v,"code":c} for c,(n,v) in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": quarter_end_str(q_now), "items": items})

    out = {"id":"stock_return_3y","title":"종목별 3년 누적 수익률 순위","mode":"ranking",
           "type":"race_chart","unit":"%",
           "updated":date.today().isoformat(),"source":"FinanceDataReader",
           "timeline":timeline}
    save(out, "stock_return_3y.json")

# ══════════════════════════════════════════════════════════════════════════════
# 5. 거래량 순위 (분기 평균 일 거래량, 만주)
# ══════════════════════════════════════════════════════════════════════════════
def build_volume(stocks):
    quarterly = {}
    for doc in stocks:
        code, name = doc["id"], doc["name"]
        q_vols = {}
        for r in doc.get("series", []):
            if "v" not in r: continue
            q = quarter_label(r["d"])
            q_vols.setdefault(q, []).append(r["v"])
        for q, vols in q_vols.items():
            if len(vols) < 10: continue
            avg_v = round(sum(vols)/len(vols)/10000, 1)  # 만주
            quarterly.setdefault(q, {})[code] = (name, avg_v)

    timeline = []
    for q in sorted(quarterly):
        entries = quarterly[q]
        if len(entries) < 3: continue
        items = sorted(
            [{"name":n,"value":v,"code":c} for c,(n,v) in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": quarter_end_str(q), "items": items})

    out = {"id":"stock_volume","title":"종목별 거래량 순위","mode":"ranking",
           "type":"race_chart","unit":"만주",
           "updated":date.today().isoformat(),"source":"FinanceDataReader",
           "timeline":timeline}
    save(out, "stock_volume.json")

# ══════════════════════════════════════════════════════════════════════════════
# 6. 거래대금 순위 (분기 평균 일 거래대금, 억원)
# ══════════════════════════════════════════════════════════════════════════════
def build_tradevalue(stocks):
    quarterly = {}
    for doc in stocks:
        code, name = doc["id"], doc["name"]
        q_tv = {}
        for r in doc.get("series", []):
            if "v" not in r or "c" not in r: continue
            tv = r["v"] * r["c"] / 1e8  # 억원
            q = quarter_label(r["d"])
            q_tv.setdefault(q, []).append(tv)
        for q, tvs in q_tv.items():
            if len(tvs) < 10: continue
            avg_tv = round(sum(tvs)/len(tvs), 0)
            quarterly.setdefault(q, {})[code] = (name, avg_tv)

    timeline = []
    for q in sorted(quarterly):
        entries = quarterly[q]
        if len(entries) < 3: continue
        items = sorted(
            [{"name":n,"value":v,"code":c} for c,(n,v) in entries.items()],
            key=lambda x:-x["value"])
        timeline.append({"date": quarter_end_str(q), "items": items})

    out = {"id":"stock_tradevalue","title":"종목별 거래대금 순위","mode":"ranking",
           "type":"race_chart","unit":"억원",
           "updated":date.today().isoformat(),"source":"FinanceDataReader",
           "timeline":timeline}
    save(out, "stock_tradevalue.json")

# ══════════════════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════════════════
def main():
    RACE_DIR.mkdir(parents=True, exist_ok=True)
    stocks = load_stocks()
    print(f"종목 {len(stocks)}개 로드\n")

    print("▶ 1. 전체 시가총액")
    build_marketcap(stocks)

    print("▶ 2. 섹터별 시가총액")
    build_sector_marketcap(stocks)

    print("▶ 3. 연간 수익률 (YTD)")
    build_return_ytd(stocks)

    print("▶ 4. 3년 누적 수익률")
    build_return_3y(stocks)

    print("▶ 5. 거래량 순위")
    build_volume(stocks)

    print("▶ 6. 거래대금 순위")
    build_tradevalue(stocks)

    print("▶ 7-12. 섹터 내부 순위")
    META = {
        "sector_semi":     ("반도체·전자 섹터 내 시가총액 순위",     "조원"),
        "sector_battery":  ("배터리·에너지 섹터 내 시가총액 순위",   "조원"),
        "sector_bio":      ("바이오·헬스케어 섹터 내 시가총액 순위", "조원"),
        "sector_auto":     ("자동차·모빌리티 섹터 내 시가총액 순위", "조원"),
        "sector_finance":  ("금융·보험 섹터 내 시가총액 순위",       "조원"),
        "sector_internet": ("인터넷·플랫폼 섹터 내 시가총액 순위",   "조원"),
    }
    for sid, codes in SECTOR_RACES.items():
        title, unit = META[sid]
        build_marketcap(stocks, codes_filter=set(codes),
                        fname=f"{sid}.json", title=title, unit=unit)

    print("\n모든 레이스 데이터 생성 완료")

if __name__ == "__main__":
    main()
