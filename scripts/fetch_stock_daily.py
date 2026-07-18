"""
fetch_stock_daily.py
두 소스 병합:
  1. FinanceDataReader  (2014~현재, 가격 데이터)
  2. 금융위원회 API     (2020~현재, 시가총액 포함 — 증분 우선)
CI: 환경변수 DATA_GO_KR_KEY / 로컬: api_keys.json
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json, os, time, requests
from datetime import date, timedelta
from pathlib import Path

# ── 상수 ────────────────────────────────────────────────────────────
ENDPOINT   = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
BEGIN_DATE = "2000-01-01"   # FDR용 (실제 제공은 2014년부터)
GOV_BEGIN  = "20200101"     # 금융위 API 실제 제공 시작일
OUT_DIR    = Path(__file__).parent.parent / "data" / "stocks"
TARGETS_F  = Path(__file__).parent / "targets.json"
KEY_FILE   = Path(__file__).parent.parent / "api_keys.json"
SLEEP_SEC  = 0.25

FATAL_CODES = {"22", "30", "31"}
SKIP_CODES  = {"10"}

# ── API 키 로드 ──────────────────────────────────────────────────────
def load_api_key():
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if key:
        print("[key] 환경변수 DATA_GO_KR_KEY 사용")
        return key
    if KEY_FILE.exists():
        with open(KEY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        key = data.get("금융위원회", {}).get("api_key", "").strip()
        if key:
            print(f"[key] api_keys.json 사용: {key[:8]}...")
            return key
    raise RuntimeError("API 키 없음. DATA_GO_KR_KEY 또는 api_keys.json 확인")

# ── 기존 JSON 로드 ────────────────────────────────────────────────────
def load_existing(code: str):
    path = OUT_DIR / f"{code}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def last_date_str(existing) -> str:
    """기존 데이터 마지막 basDt. 없으면 None."""
    if not existing or not existing.get("series"):
        return None
    return existing["series"][-1]["d"]

# ── FDR 전체 수집 ─────────────────────────────────────────────────────
def fetch_fdr(code: str, begin_date: str):
    """FinanceDataReader로 전체 기간 수집. 실패 시 [] 반환."""
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(code, begin_date)
        if df is None or df.empty:
            return []
        # DataFrame → 레코드 리스트
        records = []
        for dt, row in df.iterrows():
            d = dt.strftime("%Y%m%d")
            try:
                c = int(row["Close"]) if row["Close"] == row["Close"] else None
                o = int(row["Open"])  if row["Open"]  == row["Open"]  else None
                h = int(row["High"])  if row["High"]  == row["High"]  else None
                l = int(row["Low"])   if row["Low"]   == row["Low"]   else None
                v = int(row["Volume"]) if row["Volume"] == row["Volume"] else None
            except (ValueError, TypeError):
                continue
            rec = {"d": d}
            if c is not None: rec["c"] = c
            if o is not None: rec["o"] = o
            if h is not None: rec["h"] = h
            if l is not None: rec["l"] = l
            if v is not None: rec["v"] = v
            # mc 없음 (FDR 미제공)
            records.append(rec)
        print(f"  [FDR] {len(records)}건")
        return records
    except ImportError:
        print("  [FDR] 미설치 — 금융위 API만 사용")
        return []
    except Exception as e:
        print(f"  [FDR] 실패: {e}")
        return []

# ── 금융위 API ─────────────────────────────────────────────────────────
def fetch_gov_page(api_key, code, begin, end, page, num=1000):
    params = {
        "serviceKey": api_key, "numOfRows": num, "pageNo": page,
        "resultType": "json", "likeSrtnCd": code,
        "beginBasDt": begin, "endBasDt": end,
    }
    resp = requests.get(ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def parse_gov_response(body, code):
    header     = body.get("response", {}).get("header", {})
    result_code = header.get("resultCode", "99")
    result_msg  = header.get("resultMsg", "")
    if result_code in FATAL_CODES:
        raise RuntimeError(f"[FATAL {result_code}] {result_msg}")
    if result_code in SKIP_CODES:
        print(f"  [SKIP {result_code}] {result_msg}")
        return None, 0
    body_data   = body.get("response", {}).get("body", {})
    total       = int(body_data.get("totalCount", 0))
    items_raw   = body_data.get("items", {})
    items       = items_raw.get("item", []) if items_raw else []
    if isinstance(items, dict):
        items = [items]
    return items, total

def fetch_gov(api_key, code, begin, end):
    """금융위 API로 기간 수집."""
    print(f"  [GOV] {begin} ~ {end}")
    all_items, page = [], 1
    while True:
        body = fetch_gov_page(api_key, code, begin, end, page)
        items, total = parse_gov_response(body, code)
        if items is None:
            return None
        matched = [r for r in items if r.get("srtnCd", "").lstrip("A") == code]
        all_items.extend(matched)
        if (page - 1) * 1000 + len(items) >= total or not items:
            break
        page += 1
        time.sleep(SLEEP_SEC)
    print(f"  [GOV] {len(all_items)}건 수집")
    return all_items

def gov_item_to_record(item):
    def iv(k):
        v = item.get(k, "")
        try:
            return int(v) if v not in ("", None) else None
        except (ValueError, TypeError):
            return None
    rec = {
        "d":  item.get("basDt", ""),
        "c":  iv("clpr"), "o": iv("mkp"),
        "h":  iv("hipr"), "l": iv("lopr"),
        "v":  iv("trqu"), "mc": iv("mrktTotAmt"),
    }
    return {k: v for k, v in rec.items() if v is not None}

# ── 병합 & 저장 ────────────────────────────────────────────────────────
def merge_and_save(code, name, market, isin, existing, fdr_records, gov_items):
    """FDR + 금융위 + 기존 데이터 병합. 중복 날짜는 금융위 우선."""
    merged = {}

    # 기존 데이터 로드
    for r in (existing or {}).get("series", []):
        merged[r["d"]] = r

    # FDR 적용 (낮은 우선순위)
    for r in fdr_records:
        if r.get("d") and r["d"] not in merged:
            merged[r["d"]] = r

    # 금융위 적용 (높은 우선순위 — mc 포함)
    for item in (gov_items or []):
        r = gov_item_to_record(item)
        if r.get("d"):
            existing_r = merged.get(r["d"], {})
            merged[r["d"]] = {**existing_r, **r}  # gov가 덮어씀

    series = sorted(merged.values(), key=lambda r: r["d"])

    out = {
        "id":      code,
        "isin":    isin or (existing or {}).get("isin", ""),
        "name":    name,
        "market":  market or (existing or {}).get("market", ""),
        "sector":  (existing or {}).get("sector", ""),
        "unit":    "KRW",
        "mode":    "price",
        "updated": date.today().strftime("%Y-%m-%d"),
        "source":  "FinanceDataReader + 금융위원회_주식시세정보",
        "series":  series,
    }
    path = OUT_DIR / f"{code}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    kb = path.stat().st_size / 1024
    first = series[0]["d"] if series else "none"
    last  = series[-1]["d"] if series else "none"
    print(f"  [OK] {path.name}  {len(series)}건  {first}~{last}  {kb:.1f}KB")
    return out

# ── index.json ────────────────────────────────────────────────────────
def build_index(docs):
    items = [{
        "id":     d["id"],
        "name":   d["name"],
        "market": d["market"],
        "sector": d.get("sector", ""),
        "from":   d["series"][0]["d"]  if d.get("series") else "",
        "to":     d["series"][-1]["d"] if d.get("series") else "",
    } for d in docs]
    index = {"updated": date.today().strftime("%Y-%m-%d"), "count": len(items), "items": items}
    path = OUT_DIR / "index.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] index.json  {len(items)}종목")

# ── 메인 ─────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    today_str = date.today().strftime("%Y%m%d")

    with open(TARGETS_F, encoding="utf-8") as f:
        targets = json.load(f)["stocks"]

    print(f"\n대상 {len(targets)}종목  기준일 {today_str}\n" + "-" * 50)

    stock_docs, skipped = [], []

    for t in targets:
        code, name = t["code"], t["name"]
        print(f"\n[{code}] {name}")

        existing  = load_existing(code)
        last_d    = last_date_str(existing)
        has_fdr   = existing and len(existing.get("series", [])) > 1604  # FDR 통합 여부 추정

        # ── FDR 수집 (최초 또는 FDR 미통합) ──
        fdr_records = []
        if not has_fdr:
            fdr_records = fetch_fdr(code, BEGIN_DATE)

        # ── 금융위 증분 수집 ──
        if last_d:
            d_obj = date(int(last_d[:4]), int(last_d[4:6]), int(last_d[6:8]))
            gov_begin = (d_obj + timedelta(days=1)).strftime("%Y%m%d")
        else:
            gov_begin = GOV_BEGIN

        gov_items = []
        if gov_begin <= today_str:
            try:
                result = fetch_gov(api_key, code, gov_begin, today_str)
                if result is None:
                    skipped.append(code)
                    continue
                gov_items = result
            except RuntimeError as e:
                print(f"  [X] {e}")
                raise

        # 메타 추출
        first_gov = gov_items[0] if gov_items else {}
        isin      = first_gov.get("isinCd", "")
        market    = first_gov.get("mrktCtg", "")

        doc = merge_and_save(code, name, market, isin, existing, fdr_records, gov_items)
        stock_docs.append(doc)

        time.sleep(SLEEP_SEC)

    build_index(stock_docs)

    print("\n" + "=" * 50)
    print(f"완료: {len(stock_docs)}종목, {len(skipped)}종목 건너뜀")
    if skipped:
        print(f"건너뜀: {skipped}")

if __name__ == "__main__":
    main()
