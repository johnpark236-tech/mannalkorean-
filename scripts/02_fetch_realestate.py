"""
부동산 실거래가 데이터 수집 스크립트
출처: 국토교통부 실거래가 공개시스템 (data.go.kr)
사용: python 02_fetch_realestate.py --mode test --api all
"""
import json, os, time, argparse, sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import requests
import pandas as pd

# ─── 경로 설정 ──────────────────────────────────────────
BASE_DIR   = r"D:\logofchoices"
KEY_FILE   = os.path.join(BASE_DIR, "api_keys.json")
OUT_DIR    = os.path.join(BASE_DIR, "data", "realestate")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── API 정의 ────────────────────────────────────────────
APIS = {
    "apt_trade": {
        "name":    "아파트 매매",
        "url":     "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
        "columns": ["지역코드","시군구명","법정동","아파트명","전용면적","층","건축년도","거래년","거래월","거래일","거래금액_만원","지번"],
    },
    "apt_rent": {
        "name":    "아파트 전월세",
        "url":     "https://apis.data.go.kr/1613000/RTMSDataSvcAptRentDev/getRTMSDataSvcAptRentDev",
        "columns": ["지역코드","시군구명","법정동","아파트명","전용면적","층","거래년","거래월","거래일","보증금_만원","월세_만원","계약구분"],
    },
    "commercial_trade": {
        "name":    "상업업무용 매매",
        "url":     "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTradeDev/getRTMSDataSvcNrgTradeDev",
        "columns": ["지역코드","시군구명","법정동","용도","전용면적","층","건축년도","거래년","거래월","거래일","거래금액_만원","지번"],
    },
    "officetel_trade": {
        "name":    "오피스텔 매매",
        "url":     "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTradeDev/getRTMSDataSvcOffiTradeDev",
        "columns": ["지역코드","시군구명","법정동","오피스텔명","전용면적","층","건축년도","거래년","거래월","거래일","거래금액_만원","지번"],
    },
}

# ─── 수집 지역 ──────────────────────────────────────────
REGIONS = {
    "11110": "서울 종로구",
    "11140": "서울 중구",
    "11680": "서울 강남구",
    "26110": "부산 중구",
    "41135": "경기 성남 분당구",
}

# ─── 에러코드 처리 방침 ──────────────────────────────────
ERR_RETRY = {"01"}           # 재시도
ERR_SKIP  = {"10", "99"}    # 파라미터 오류/미지 → skip
ERR_WAIT  = {"22"}           # 요청 제한 → 1분 대기 후 재시도
ERR_FATAL = {"12","20","30","31","32"}  # 즉시 중단


def load_api_key():
    if not os.path.exists(KEY_FILE):
        sys.exit(f"[오류] {KEY_FILE} 파일이 없습니다.")
    with open(KEY_FILE, encoding="utf-8") as f:
        keys = json.load(f)

    def _valid(k):
        return k and not k.startswith("여기에") and k.lower() not in ("", "none", "placeholder")

    # 1순위: 국토교통부_실거래가 전용 슬롯
    key = keys.get("국토교통부_실거래가", {}).get("api_key", "").strip()
    if _valid(key):
        print(f"[키] 국토교통부_실거래가 슬롯 사용")
        return key

    # 2순위: 공공데이터포털 공통키 (금융위원회와 동일)
    key = keys.get("금융위원회", {}).get("api_key", "").strip()
    if _valid(key):
        print(f"[키] 공공데이터포털 공통키(금융위원회) 사용")
        return key

    sys.exit(
        "[안내] api_keys.json 에 유효한 공공데이터포털 인증키가 없습니다.\n"
        "  data.go.kr 마이페이지 → 인증키 발급 후 금융위원회.api_key 에 입력하세요."
    )


def get_periods(mode):
    today = date.today()
    if mode == "test":
        # 최근 3개월
        start = today - relativedelta(months=3)
    else:
        # 2020-01 ~ 현재
        start = date(2020, 1, 1)
    periods = []
    cur = date(start.year, start.month, 1)
    end = date(today.year, today.month, 1)
    while cur <= end:
        periods.append(cur.strftime("%Y%m"))
        cur += relativedelta(months=1)
    return periods


def load_checkpoint(api_key_name):
    path = os.path.join(OUT_DIR, f".checkpoint_{api_key_name}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_checkpoint(api_key_name, data):
    path = os.path.join(OUT_DIR, f".checkpoint_{api_key_name}.json")
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_one(url, service_key, lawd_cd, deal_ymd, page=1, num_rows=1000, retries=3):
    """단일 API 페이지 호출. (item list, total_count) 반환"""
    params = {
        "serviceKey": service_key,
        "LAWD_CD":    lawd_cd,
        "DEAL_YMD":   deal_ymd,
        "pageNo":     page,
        "numOfRows":  num_rows,
        "type":       "json",
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            body = r.json().get("response", {})
            header = body.get("header", {})
            code   = str(header.get("resultCode", "99"))
            msg    = header.get("resultMsg", "")

            if code == "00":
                bd    = body.get("body", {})
                total = int(bd.get("totalCount", 0))
                raw   = bd.get("items", {})
                # 빈 응답 처리
                if not raw or raw == "":
                    return [], 0
                items = raw.get("item", [])
                if isinstance(items, dict):   # 단건이면 dict로 오는 경우
                    items = [items]
                return items, total

            elif code in ERR_FATAL:
                sys.exit(f"[치명 오류] {code}: {msg} — 프로세스를 종료합니다.")

            elif code in ERR_WAIT:
                print(f"  [요청제한 {code}] 1분 대기 후 재시도…")
                time.sleep(60)
                continue

            elif code in ERR_SKIP:
                print(f"  [SKIP {code}] {msg} (LAWD={lawd_cd}, YMD={deal_ymd})")
                return [], 0

            else:  # ERR_RETRY or unknown
                wait = 2 ** attempt
                print(f"  [재시도 {attempt}/{retries}] {code}: {msg} — {wait}s 대기")
                time.sleep(wait)

        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            print(f"  [Timeout 재시도 {attempt}/{retries}] {wait}s 대기")
            time.sleep(wait)
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [에러 재시도 {attempt}/{retries}] {e} — {wait}s 대기")
            time.sleep(wait)

    print(f"  [포기] {lawd_cd} / {deal_ymd} page={page} — 수집 실패, 건너뜀")
    return [], 0


def parse_amount(val):
    """거래금액 쉼표 제거 후 정수 변환"""
    try:
        return int(str(val).replace(",", "").strip())
    except:
        return None


def extract_row(api_name, lawd_cd, item):
    region_name = REGIONS.get(lawd_cd, lawd_cd)
    if api_name == "apt_trade":
        return {
            "지역코드":     lawd_cd,
            "시군구명":     region_name,
            "법정동":       item.get("umdNm", "").strip(),
            "아파트명":     item.get("aptNm", "").strip(),
            "전용면적":     item.get("excluUseAr", ""),
            "층":           item.get("floor", ""),
            "건축년도":     item.get("buildYear", ""),
            "거래년":       item.get("dealYear", ""),
            "거래월":       item.get("dealMonth", ""),
            "거래일":       str(item.get("dealDay", "")).strip(),
            "거래금액_만원": parse_amount(item.get("dealAmount", 0)),
            "지번":         item.get("jibun", "").strip(),
        }
    elif api_name == "apt_rent":
        return {
            "지역코드":   lawd_cd,
            "시군구명":   region_name,
            "법정동":     item.get("umdNm", "").strip(),
            "아파트명":   item.get("aptNm", "").strip(),
            "전용면적":   item.get("excluUseAr", ""),
            "층":         item.get("floor", ""),
            "거래년":     item.get("dealYear", ""),
            "거래월":     item.get("dealMonth", ""),
            "거래일":     str(item.get("dealDay", "")).strip(),
            "보증금_만원": parse_amount(item.get("deposit", 0)),
            "월세_만원":   parse_amount(item.get("monthlyRent", 0)),
            "계약구분":   item.get("contractType", "").strip(),
        }
    elif api_name == "commercial_trade":
        return {
            "지역코드":     lawd_cd,
            "시군구명":     item.get("sggNm", region_name).strip(),
            "법정동":       item.get("umdNm", "").strip(),
            "용도":         item.get("type", "").strip(),
            "전용면적":     item.get("excluUseAr", ""),
            "층":           item.get("floor", ""),
            "건축년도":     item.get("buildYear", ""),
            "거래년":       item.get("dealYear", ""),
            "거래월":       item.get("dealMonth", ""),
            "거래일":       str(item.get("dealDay", "")).strip(),
            "거래금액_만원": parse_amount(item.get("dealAmount", 0)),
            "지번":         item.get("jibun", "").strip(),
        }
    elif api_name == "officetel_trade":
        return {
            "지역코드":     lawd_cd,
            "시군구명":     region_name,
            "법정동":       item.get("umdNm", "").strip(),
            "오피스텔명":   item.get("offiNm", "").strip(),
            "전용면적":     item.get("excluUseAr", ""),
            "층":           item.get("floor", ""),
            "건축년도":     item.get("buildYear", ""),
            "거래년":       item.get("dealYear", ""),
            "거래월":       item.get("dealMonth", ""),
            "거래일":       str(item.get("dealDay", "")).strip(),
            "거래금액_만원": parse_amount(item.get("dealAmount", 0)),
            "지번":         item.get("jibun", "").strip(),
        }
    return {}


def collect_api(api_name, service_key, periods, start_ym, end_ym):
    api   = APIS[api_name]
    url   = api["url"]
    cols  = api["columns"]

    ckpt  = load_checkpoint(api_name)
    rows  = []
    total_count = 0

    print(f"\n{'='*60}")
    print(f"  [{api['name']}] {start_ym} ~ {end_ym}  지역 {len(REGIONS)}개")
    print(f"{'='*60}")

    for lawd_cd, region_name in REGIONS.items():
        for ym in periods:
            ck_key = f"{lawd_cd}_{ym}"

            # checkpoint: 이미 수집된 항목 건너뜀
            if ckpt.get(ck_key) == "done":
                continue

            print(f"  [{region_name}] {ym} 수집 중…", end="", flush=True)

            page = 1
            month_rows = []
            while True:
                items, total = fetch_one(url, service_key, lawd_cd, ym, page=page)
                for it in items:
                    row = extract_row(api_name, lawd_cd, it)
                    if row:
                        month_rows.append(row)

                fetched_so_far = (page - 1) * 1000 + len(items)
                if total == 0 or fetched_so_far >= total:
                    break
                page += 1
                time.sleep(0.3)   # 페이지 간 짧은 슬립

            rows.extend(month_rows)
            total_count += len(month_rows)
            print(f" {len(month_rows)}건 (누적: {total_count:,}건)")

            ckpt[ck_key] = "done"
            save_checkpoint(api_name, ckpt)

            time.sleep(0.5)   # rate limiting

    if not rows:
        print(f"  수집 결과 없음.")
        return

    fname = f"{api_name}_{start_ym}_{end_ym}.csv"
    fpath = os.path.join(OUT_DIR, fname)
    df = pd.DataFrame(rows, columns=cols)
    df.to_csv(fpath, index=False, encoding="utf-8-sig")
    print(f"\n  저장 완료: {fpath}  ({len(df):,}행)")


def main():
    parser = argparse.ArgumentParser(description="부동산 실거래가 수집")
    parser.add_argument("--mode", choices=["test","full"], default="test",
                        help="test=최근 3개월 / full=2020.01~현재")
    parser.add_argument("--api",  default="all",
                        help="all / apt_trade / apt_rent / commercial_trade / officetel_trade")
    args = parser.parse_args()

    service_key = load_api_key()
    periods     = get_periods(args.mode)
    start_ym    = periods[0]
    end_ym      = periods[-1]

    print(f"[부동산 실거래가 수집 시작]")
    print(f"  모드: {args.mode}  |  기간: {start_ym} ~ {end_ym}  ({len(periods)}개월)")
    print(f"  API: {args.api}")

    targets = list(APIS.keys()) if args.api == "all" else [args.api]
    for t in targets:
        if t not in APIS:
            print(f"[오류] 알 수 없는 API: {t}  (선택: {', '.join(APIS)})")
            continue
        collect_api(t, service_key, periods, start_ym, end_ym)

    print("\n[완료] 모든 수집 작업이 끝났습니다.")
    print("  다음 단계: python 03_transform_for_flourish.py")
    print("  출처 표기: 국토교통부 실거래가 공개시스템")


if __name__ == "__main__":
    main()
