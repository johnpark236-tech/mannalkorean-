# 1,582개 확정 섹터 병합 → stocks_sector_final.csv 업데이트 → chart_viewer.html STOCKS_DB 재생성
import sys, os, re, json, pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

MASTER_CSV = r'D:\logofchoices\data\csv\stocks_sector_final.csv'
FINAL_XLSX = r'D:\logofchoices\data\csv\stocks_sector_FINAL.xlsx'
HTML_FILE  = r'D:\logofchoices\chart_viewer.html'

# ─── 1. 마스터 CSV 로드 ─────────────────────────────
print('[1] 마스터 CSV 로드...')
master = pd.read_csv(MASTER_CSV, encoding='utf-8-sig', dtype=str)
master['종목코드'] = master['종목코드'].str.strip().str.zfill(6)
print(f'   → {len(master)}개  (S20: {(master["섹터코드"]=="S20").sum()}개)')

# ─── 2. FINAL xlsx 로드 ────────────────────────────
print('[2] FINAL xlsx 로드 (전체분류 시트)...')
final = pd.read_excel(FINAL_XLSX, sheet_name='전체분류', dtype=str)
final['종목코드'] = final['종목코드'].str.strip()

# 특수코드(알파벳 포함)는 zfill 제외
def safe_zfill(code):
    s = str(code).strip()
    if s.replace('.','').isdigit():
        try:
            return str(int(float(s))).zfill(6)
        except:
            return s
    return s

final['종목코드'] = final['종목코드'].apply(safe_zfill)
print(f'   → {len(final)}개')

# ─── 3. 병합: 종목코드 기준으로 섹터 업데이트 ───────────
print('[3] 섹터 업데이트 병합...')
final_map = final.set_index('종목코드')[['섹터코드','섹터명','분류근거','검토신뢰도']].to_dict('index')

updated = 0
not_found = []
for idx, row in master.iterrows():
    code = row['종목코드']
    if code in final_map:
        info = final_map[code]
        master.at[idx, '섹터코드']   = info['섹터코드']
        master.at[idx, '섹터명']     = info['섹터명']
        master.at[idx, '분류근거']   = info.get('분류근거', 'AI+수동검토')
        master.at[idx, '검토신뢰도'] = info.get('검토신뢰도', '높음')
        master.at[idx, '매칭방식']   = 'AI+수동검토'
        updated += 1

print(f'   → {updated}개 업데이트')
print(f'   → S20 잔여: {(master["섹터코드"]=="S20").sum()}개')

# 코드 미매칭 확인 (마스터에 있는 final 코드 중 못 찾은 것)
master_codes = set(master['종목코드'])
for code in final_map:
    if code not in master_codes:
        not_found.append(code)
if not_found:
    print(f'   [경고] 마스터에 없는 코드: {not_found[:10]}...')

# ─── 4. 정렬 및 저장 ───────────────────────────────
print('[4] 업데이트된 CSV 저장...')
master = master.sort_values(['섹터코드','시장','종목명']).reset_index(drop=True)
master.to_csv(MASTER_CSV, index=False, encoding='utf-8-sig')
print(f'   → {MASTER_CSV}')

# ─── 5. 섹터 분포 ──────────────────────────────────
print('\n=== 최종 섹터 분포 (2,766개) ===')
dist = master['섹터코드'].value_counts().sort_index()
for code, cnt in dist.items():
    print(f'  {code}: {cnt:>4}')
print(f'  합계: {len(master)}')

# ─── 6. chart_viewer.html STOCKS_DB 재생성 ─────────
print('\n[6] chart_viewer.html STOCKS_DB 업데이트...')
with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

# STOCKS_DB JS 배열 생성
rows_js = []
for _, row in master.iterrows():
    n = str(row['종목명']).replace('\\','\\\\').replace('"','\\"')
    c = str(row['종목코드'])
    m = str(row['시장'])
    s = str(row['섹터코드'])
    rows_js.append(f'{{n:"{n}",c:"{c}",m:"{m}",s:"{s}"}}')

new_db = 'const STOCKS_DB = [\n  ' + ',\n  '.join(rows_js) + '\n];'

# 기존 STOCKS_DB 교체 (인덱스 방식 - \w 이슈 방지)
pattern = r'const STOCKS_DB\s*=\s*\[[\s\S]*?\];'
m = re.search(pattern, html)
if m:
    html = html[:m.start()] + new_db + html[m.end():]
    print('   → STOCKS_DB 교체 성공')
else:
    print('   [오류] STOCKS_DB 패턴을 찾지 못함')
    sys.exit(1)

with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

file_kb = os.path.getsize(HTML_FILE) // 1024
print(f'   → {HTML_FILE} ({file_kb:,} KB)')

# ─── 7. 최종 검증 ───────────────────────────────────
print('\n=== 최종 검증 ===')
checks = {
    '마스터 종목수 = 2,766': len(master) == 2766,
    f'업데이트 수 = 1,582': updated == 1582,
    'S20 잔여 ≤ 1,582': (master['섹터코드']=='S20').sum() <= 1582,
    'S99 = 0': (master['섹터코드']=='S99').sum() == 0,
    'STOCKS_DB 교체됨': new_db[:30] in html,
}
all_ok = True
for msg, ok in checks.items():
    print(f'  [{"OK" if ok else "NG"}] {msg}')
    if not ok: all_ok = False

print(f'\n{">>> 모든 작업 완료!" if all_ok else ">>> 일부 항목 확인 필요"}')
