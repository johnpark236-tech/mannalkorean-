import json
import os
import time
import requests
import pandas as pd
from datetime import date, timedelta

# --- 설정 ---
API_KEY_FILE = r"D:\logofchoices\api_keys.json"
OUTPUT_DIR_RAW = r"D:\logofchoices\data\raw"
OUTPUT_DIR_CSV = r"D:\logofchoices\data\csv"
OUTPUT_DIR_FLOURISH = r"D:\logofchoices\flourish"

ENDPOINT = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"

# 수집 대상 종목: 이름 -> (정확한 종목코드, 검색용 이름)
# srtnCd 필터는 API에서 작동하지 않으므로 likeItmsNm + srtnCd 교차 검증 사용
STOCKS = {
    "삼성전자":       ("005930", "삼성전자"),
    "SK하이닉스":     ("000660", "SK하이닉스"),
    "LG에너지솔루션": ("373220", "LG에너지솔루션"),
}


def get_month_end_dates(start_year=2020, end_year=2024):
    dates = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if month == 12:
                last_day = date(year, 12, 31)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)
            dates.append(last_day.strftime("%Y%m%d"))
    return dates


def load_api_key():
    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        keys = json.load(f)
    return keys["금융위원회"]["api_key"]


def fetch_stock_price(api_key, stock_code, search_name, bas_dt):
    """likeItmsNm 으로 검색 후 srtnCd 로 교차 검증."""
    params = {
        "serviceKey": api_key,
        "basDt": bas_dt,
        "likeItmsNm": search_name,
        "numOfRows": 10,
        "resultType": "json",
    }
    try:
        resp = requests.get(ENDPOINT, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not items:
            return None
        if isinstance(items, dict):
            items = [items]
        # srtnCd 정확 일치 항목 선택
        for item in items:
            if item.get("srtnCd") == stock_code:
                return {
                    "basDt": item.get("basDt"),
                    "srtnCd": item.get("srtnCd"),
                    "itmsNm": item.get("itmsNm"),
                    "clpr": int(item.get("clpr", "0").replace(",", "")),
                    "mrktTotAmt": int(item.get("mrktTotAmt", "0").replace(",", "")),
                }
        return None
    except requests.RequestException as e:
        print(f"  [오류] API 호출 실패 ({stock_code}, {bas_dt}): {e}")
        return None
    except (KeyError, ValueError, AttributeError) as e:
        print(f"  [오류] 파싱 실패 ({stock_code}, {bas_dt}): {e}")
        return None


def find_nearest_trading_day(api_key, stock_code, search_name, target_date_str, lookback=5):
    """월말이 휴장일이면 최대 lookback 영업일 전까지 역방향 탐색."""
    target = date(int(target_date_str[:4]), int(target_date_str[4:6]), int(target_date_str[6:]))
    for i in range(lookback):
        d = target - timedelta(days=i)
        result = fetch_stock_price(api_key, stock_code, search_name, d.strftime("%Y%m%d"))
        if result:
            return result
    return None


def main():
    print("=== Log of Choices - 주식 종가 데이터 수집 시작 ===\n")

    try:
        api_key = load_api_key()
        print("[OK] API 키 로드 완료")
    except (FileNotFoundError, KeyError) as e:
        print(f"[실패] API 키 로드 오류: {e}")
        return

    month_end_dates = get_month_end_dates(2020, 2024)
    print(f"[INFO] 수집 대상: {len(month_end_dates)}개 월말 날짜 x {len(STOCKS)}개 종목\n")

    all_records = []

    for stock_name, (stock_code, search_name) in STOCKS.items():
        print(f"[수집 중] {stock_name} ({stock_code})")
        found = 0
        missing = 0
        for bas_dt in month_end_dates:
            result = find_nearest_trading_day(api_key, stock_code, search_name, bas_dt)
            if result:
                result["stock_name"] = stock_name
                all_records.append(result)
                found += 1
            else:
                missing += 1
            time.sleep(0.05)
        print(f"  -> 완료 (수집: {found}건, 미수집: {missing}건)\n")

    if not all_records:
        print("[경고] 수집된 데이터가 없습니다. API 키와 네트워크를 확인하세요.")
        return

    # --- 원본 CSV 저장 ---
    df = pd.DataFrame(all_records)
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d")
    df["year_month"] = df["basDt"].dt.to_period("M").astype(str)
    df = df.sort_values(["stock_name", "basDt"])

    raw_csv_path = os.path.join(OUTPUT_DIR_CSV, "samsung_skhynix_close.csv")
    df.to_csv(raw_csv_path, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 원본 CSV: {raw_csv_path}  ({len(df)}행)")

    # --- Flourish 바 차트 레이스용 CSV ---
    # 행: 종목명, 열: YYYY-MM, 값: 종가(원)
    pivot = df.pivot_table(index="stock_name", columns="year_month", values="clpr", aggfunc="last")
    pivot = pivot.reset_index().rename(columns={"stock_name": "Label"})
    pivot.columns.name = None

    flourish_path = os.path.join(OUTPUT_DIR_FLOURISH, "stock_race.csv")
    pivot.to_csv(flourish_path, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] Flourish CSV: {flourish_path}  ({pivot.shape[0]}행 x {pivot.shape[1]}열)")

    # --- 원본 JSON 백업 ---
    raw_json_path = os.path.join(OUTPUT_DIR_RAW, "stock_records.json")
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2, default=str)
    print(f"[저장 완료] 원본 JSON: {raw_json_path}")

    # --- 간단 통계 출력 ---
    print("\n=== 완료 ===")
    print(f"수집 종목: {', '.join(STOCKS.keys())}")
    print(f"수집 기간: 2020-01 ~ 2024-12 (월말 기준)")
    print(f"총 레코드: {len(all_records)}건")
    print("\n[종목별 최신 종가]")
    latest = df.groupby("stock_name").last()[["basDt", "clpr", "mrktTotAmt"]]
    for name, row in latest.iterrows():
        mkt = row["mrktTotAmt"] / 1e12
        print(f"  {name}: {row['clpr']:,}원  (시가총액 {mkt:.1f}조원, {row['basDt'].date()})")


if __name__ == "__main__":
    main()
