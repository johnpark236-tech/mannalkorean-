# Flourish Bar Chart Race 변환 스크립트
# 입력: D:/logofchoices/data/realestate/apt_trade_*.csv
# 출력: D:/logofchoices/data/realestate/flourish_*.csv
# 사용: python 03_transform_for_flourish.py --api apt_trade
import os, glob, argparse, sys
import pandas as pd

BASE_DIR = r"D:\logofchoices"
IN_DIR   = os.path.join(BASE_DIR, "data", "realestate")
OUT_DIR  = IN_DIR

REGION_NAMES = {
    "11110": "서울 종로구",
    "11140": "서울 중구",
    "11680": "서울 강남구",
    "26110": "부산 중구",
    "41135": "경기 성남 분당구",
}

API_AMOUNT_COL = {
    "apt_trade":        "거래금액_만원",
    "apt_rent":         "보증금_만원",
    "commercial_trade": "거래금액_만원",
    "officetel_trade":  "거래금액_만원",
}


def load_csv_files(api_name):
    pattern = os.path.join(IN_DIR, f"{api_name}_*.csv")
    files   = glob.glob(pattern)
    if not files:
        print(f"  [SKIP] {api_name}: CSV 파일 없음 ({pattern})")
        return None
    dfs = []
    for fp in sorted(files):
        try:
            df = pd.read_csv(fp, dtype=str, encoding="utf-8-sig")
            dfs.append(df)
            print(f"  로드: {os.path.basename(fp)}  ({len(df):,}행)")
        except Exception as e:
            print(f"  [경고] {fp}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else None


def build_ym(row):
    try:
        y = str(row["거래년"]).strip().zfill(4)
        m = str(row["거래월"]).strip().zfill(2)
        if y == "0000" or m == "00":
            return None
        return y + m
    except:
        return None


def transform(api_name):
    amount_col = API_AMOUNT_COL.get(api_name)
    if not amount_col:
        print(f"  [오류] 알 수 없는 API: {api_name}")
        return

    print(f"\n[{api_name}] 변환 시작…")
    df = load_csv_files(api_name)
    if df is None:
        return

    # ym 컬럼 생성
    df["ym"] = df.apply(build_ym, axis=1)
    df = df.dropna(subset=["ym"])

    # 거래금액 숫자 변환
    df[amount_col] = pd.to_numeric(
        df[amount_col].astype(str).str.replace(",", ""), errors="coerce"
    )
    df = df.dropna(subset=[amount_col])
    df = df[df[amount_col] > 0]

    # 지역코드 → 지역명 정리
    df["지역명"] = df["시군구명"].fillna(
        df["지역코드"].map(REGION_NAMES).fillna(df["지역코드"])
    )

    # 월별 × 지역별 평균 (만원)
    pivot = (
        df.groupby(["지역명", "ym"])[amount_col]
        .mean()
        .round(0)
        .astype(int)
        .unstack("ym")
    )

    # 모든 지역에 없는 달은 0이면 NaN → forward fill
    pivot = pivot.sort_index(axis=1)
    pivot = pivot.ffill(axis=1).fillna(0).astype(int)

    # Flourish 포맷: 인덱스를 "지역" 컬럼으로
    pivot.index.name = "지역"
    pivot = pivot.reset_index()

    out_fname = f"flourish_{api_name}.csv"
    out_path  = os.path.join(OUT_DIR, out_fname)
    pivot.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"  저장 완료: {out_path}")
    print(f"  크기: {pivot.shape[0]}개 지역 × {pivot.shape[1]-1}개월")
    print(f"  기간: {pivot.columns[1]} ~ {pivot.columns[-1]}")

    # 미리보기
    print(f"\n  [미리보기 — 첫 3행 × 첫 5열]")
    preview_cols = ["지역"] + list(pivot.columns[1:6])
    print(pivot[preview_cols].head(3).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Flourish Bar Chart Race 변환")
    parser.add_argument("--api", default="apt_trade",
                        help="apt_trade / apt_rent / commercial_trade / officetel_trade / all")
    args = parser.parse_args()

    targets = list(API_AMOUNT_COL.keys()) if args.api == "all" else [args.api]
    for t in targets:
        transform(t)

    print("\n[완료] Flourish CSV 변환 끝났습니다.")
    print("  Flourish에서 Bar Chart Race → Data 탭에 CSV 업로드하세요.")
    print("  출처 표기: 국토교통부 실거래가 공개시스템")


if __name__ == "__main__":
    main()
