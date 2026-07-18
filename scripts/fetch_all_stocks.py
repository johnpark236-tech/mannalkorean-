"""
전체 KOSPI/KOSDAQ 종목 수집
- 엔드포인트: GetStockSecuritiesInfoService/getStockPriceInfo (이미 승인된 API)
- GetKrxListedInfoService는 별도 신청 필요 → 여기서는 사용 안 함
"""
import json
import re
import time
import datetime
import requests

# --- API 키 로드 ---
with open(r"D:\logofchoices\api_keys.json", "r", encoding="utf-8") as f:
    keys = json.load(f)
API_KEY = keys["금융위원회"]["api_key"]

EP = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
PAGE_SIZE = 1000

# --- 섹터 자동 분류 ---
SECTOR_MAP = {
    "S01": r"반도체|하이닉스|이오테크닉스|원익IPS|한미반도체|레인보우로보틱스|HPSP|웨이퍼|OLED|기판|PCB",
    "S02": r"에너지솔루션|에코프로|배터리|전지|SDI|포스코퓨처|양극재|음극재|전해질|분리막",
    "S03": r"현대자동차|현대차(?!증권)|기아(?!타이거|타이탄)|모비스|글로비스|만도|오토(?!랜드)",
    "S04": r"중공업|조선|한화에어로|항공우주|두산에너빌|방산|방위|한화오션",
    "S05": r"금융(?!투자)|은행|보험|증권|생명(?!과학|공학)|화재(?!보험|사)|카드(?!게임)|신한지주|하나금융|우리금융|KB금융|메리츠",
    "S06": r"바이오|제약|의료|헬스케어|셀트리온|유한양행|알테오젠|HLB(?!\w)|파마리서치|클래시스|리가켐|루닛|삼천당",
    "S07": r"네이버|카카오(?!뱅크|페이)|게임(?!카드|빌)|플랫폼|크래프톤|펄어비스|넥슨|엔씨소프트|컴투스|위메이드",
    "S08": r"화학(?!바이오|제약)|소재|POSCO홀딩|포스코홀딩|고려아연|풍산(?!홀딩)|철강|비철|롯데케미",
    "S09": r"건설|부동산|삼성물산|GS건설|DL이앤씨|현대건설|개발(?!원)|시공|주택",
    "S10": r"한국전력|S-Oil|SK이노베이션|정유|가스(?!트)|발전(?!기)",
    "S11": r"롯데쇼핑|이마트|CJ제일제당|오뚜기|농심|KT&G|유통|쇼핑(?!몰)|식품|음료(?!업체)",
    "S12": r"SK텔레콤|KT(?!&G|\w)|LG유플|통신|텔레콤",
}

def guess_sector(name):
    for code, pat in SECTOR_MAP.items():
        if re.search(pat, name):
            return code
    return "S99"

def fetch_market(market, bas_dt):
    """특정 날짜 + 시장의 전체 종목 수집 (페이지네이션)"""
    all_items, page = [], 1
    while True:
        try:
            r = requests.get(EP, params={
                "serviceKey": API_KEY,
                "basDt": bas_dt,
                "mrktCls": market,
                "numOfRows": PAGE_SIZE,
                "pageNo": page,
                "resultType": "json",
            }, timeout=20)
            r.raise_for_status()
            body = r.json().get("response", {}).get("body", {})
            total = int(body.get("totalCount", 0))
            if total == 0:
                return None  # 데이터 없는 날짜 (휴장일 등)
            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            all_items.extend(items)
            print(f"  {market} {len(all_items)}/{total}건 (page {page})")
            if len(all_items) >= total:
                break
            page += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"  [오류] {market} page {page}: {e}")
            return None
    return all_items

# --- 기준일 자동 조정 (최대 7영업일 역순) ---
result = []
for market in ["KOSPI", "KOSDAQ"]:
    items = None
    used_date = None
    for delta in range(1, 8):
        d = (datetime.date.today() - datetime.timedelta(days=delta)).strftime("%Y%m%d")
        print(f"\n[수집] {market}  기준일: {d}")
        items = fetch_market(market, d)
        if items:
            used_date = d
            break
    if not items:
        print(f"[경고] {market} 데이터를 가져오지 못했습니다")
        continue
    print(f"  -> {market} {len(items)}개 종목 수집 완료 (기준: {used_date})")
    for it in items:
        code = (it.get("srtnCd") or "").strip()
        name = (it.get("itmsNm") or "").strip()
        if code and name:
            result.append({
                "n": name,
                "c": code,
                "m": market,
                "s": guess_sector(name),
            })

print(f"\n수집 결과: 총 {len(result)}개 종목")

if not result:
    print("[실패] 데이터를 가져오지 못했습니다. API 키 활성화 상태를 확인하세요.")
    exit(1)

# --- JSON 저장 ---
out_path = r"D:\logofchoices\data\csv\all_stocks.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"저장 완료: {out_path}")

# 통계
from collections import Counter
mkt_cnt = Counter(s["m"] for s in result)
sec_cnt = Counter(s["s"] for s in result)
print("\n[시장별]")
for m, n in sorted(mkt_cnt.items()):
    print(f"  {m}: {n}개")
print("\n[주요 섹터]")
for s, n in sorted(sec_cnt.items()):
    if n > 0:
        print(f"  {s}: {n}개")

# --- chart_viewer.html STOCKS_DB 자동 업데이트 ---
import re as _re

html_path = r"D:\logofchoices\chart_viewer.html"
entries = []
for s in result:
    name = s["n"].replace("'", "\\'")
    entries.append(f"  {{n:'{name}', c:'{s['c']}', m:'{s['m']}', s:'{s['s']}'}}")
new_db = "const STOCKS_DB = [\n" + ",\n".join(entries) + "\n];"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()
new_html, cnt = _re.subn(r"const STOCKS_DB = \[[\s\S]*?\n\];", new_db, html, count=1)
if cnt:
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"\n[HTML] chart_viewer.html STOCKS_DB 갱신 완료 ({len(result)}개)")
else:
    print("\n[HTML] STOCKS_DB 패턴 없음 - HTML 업데이트 건너뜀")
