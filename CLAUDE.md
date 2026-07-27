## ⚠️ API 키 관리 규칙 (절대 준수)

### 금지 ❌
- API 키 하드코딩 절대 금지
- PUBLIC_API_KEY 같은 상수로 키 직접 입력 금지
- GitHub에 실제 키 값 노출 금지

### 준수 ✅
- 모든 API 키는 D:\logofchoices\api_keys.json 에서 읽기
- 키 접근 경로: keys["금융위원회"]["api_key"]
- 농산물/주식/부동산  그외 모두 동일한 금융위원회 키 사용
- 키 읽기 순서: api_keys.json → apiKeyCache → localStorage

### 표준 코드
```js
async function loadApiKey() {
  const res = await fetch('/api_keys.json');
  const keys = await res.json();
  return keys["금융위원회"]["api_key"];
}
```

---

## 📁 파일 구조 및 작업 규칙

### 작업 파일 ✅
- **현황 시트**: `chart_viewer.html` ← 이 채팅방 전용 작업 파일

### 절대 수정 금지 ❌
- `chart_viewer_A.html` — 주식 시트 (A채팅방 전용)
- `chart_viewer_B.html` — 부동산 시트 (B채팅방 전용)
- `chart_viewer_C.html` — 농산물 시트 (C채팅방 전용)

### 파일 구조
```
D:\logofchoices\
├── chart_viewer.html      ← 현황 시트 메인 (이 채팅방)
├── chart_viewer_A.html    ← 주식 시트 (A채팅방)
├── chart_viewer_B.html    ← 부동산 시트 (B채팅방)
└── chart_viewer_C.html    ← 농산물 시트 (C채팅방)
```

### GitHub push
- 병합 완료 후 진행
- 도메인: mannalkorean.com

---

## 🔄 데이터 파이프라인 규칙 (A채팅방)

- 브라우저 코드에서 금융위 API를 직접 호출하지 않는다. (CORS 차단 + 키 노출)
- 모든 시세 데이터는 GitHub Actions ETL이 생성한 `data/stocks/*.json` 에서 읽는다.
- API 키는 GitHub Secrets(`DATA_GO_KR_KEY`)와 로컬 `api_keys.json` 에만 존재한다.
- `api_keys.json` 은 `.gitignore`에 등록되어 있으며 절대 커밋하지 않는다.

### ETL 실행
```bash
python scripts/fetch_stock_daily.py   # 로컬 실행 (api_keys.json 사용)
# CI: GitHub Actions → .github/workflows/fetch-stock.yml (매일 KST 07:00)
```

## 📊 데이터 스키마

시계열 키는 축약형 `{ d, c, o, h, l, v, mc }` 를 사용한다.

```json
{ "d": "20240102", "c": 79600, "o": 78200, "h": 79800, "l": 78200, "v": 17142000, "mc": 475103000000000 }
```

신규 카테고리 추가 시 동일 스키마를 따른다. (엔진 재사용 목적)

## 📚 Education Module 규칙 (v6.0 추가)

- 이 프로젝트는 Universal Knowledge Intelligence Platform이다
- 한국어 교육은 첫 번째 Domain Module이다
- 교재 원문은 `data/education/korean/raw/` 에만 보관 (외부 공개 금지)
- 메타데이터·정규화 결과만 서비스에 사용
- 사용자에게는 Level 3 (AI 생성) 결과만 제공
- 출처는 항상 기록: source_book, source_chapter
- 개념 카드 스키마(EDU_CONCEPT_XXX)는 Contract — 변경 금지

### Core vs Module 판단
- ETL, Knowledge DB, AI Comparison = Core (변경 금지)
- 한국어교육, 주식, 부동산 = Module (추가·교체 가능)

### Education 파일 작업 규칙
```
data/education/korean/raw/        ← 교재 원문 (gitignore, 비공개)
data/education/korean/normalized/ ← 정규화 JSON (메타데이터)
data/education/korean/markdown/   ← Markdown 검토용
data/education/korean/db/         ← SQLite DB (gitignore)
scripts/extract_korean_edu.py     ← ETL 스크립트
scripts/build_korean_edu_db.py    ← DB 구축
scripts/generate_lesson_plan.py   ← AI 교안 생성
```

---

## 🤖 Automation Engine v2.0 (2026-07-27 추가)

### 디렉토리 구조
```
D:\loc-news\                        ← GitHub Pages 발행 저장소
├── articles\YYYYMMDD_TICKER.html   ← 발행된 기사
├── assets\style.css                ← 다크 테마 CSS
├── data\published_log.json         ← 발행 이력
├── index.html                      ← 자동 재생성
└── sitemap.xml                     ← 자동 재생성

D:\loc_automation\                  ← 파이프라인 (비공개)
├── engine\publisher.py             ← HTML 생성 + git push
├── engine\processor.py             ← Claude API 기사 생성
├── scripts\run_pipeline.py         ← 실행 진입점
└── drafts\YYYYMMDD_TICKER.json     ← 수동 작성 기사 (선택)
```

### 파이프라인 우선순위
1. `drafts/YYYYMMDD_TICKER.json` 존재 → 해당 파일 사용
2. `api_keys.json`에 `anthropic.api_key` 존재 → Claude API 자동 생성
3. 둘 다 없음 → 더미 데이터로 파이프라인 테스트

### 실행 방법
```bash
cd D:\loc_automation
python scripts/run_pipeline.py --dry   # 미리보기
python scripts/run_pipeline.py         # 실제 발행
```

### 발행 타겟 종목
`TARGETS = ["005930", "000660", "035420", "035720"]`  (삼성전자·하이닉스·네이버·카카오)

### 절대 규칙
- 기사 수치는 ETL 데이터 값만 사용 (AI 창작 금지)
- **approve.py 승인 없이 직접 발행 금지** (run_pipeline → queue → approve.py 순서)
- 쿠팡 고지문구 자동 삽입 (publisher.py 내장)
- 투자 주의사항·AI 생성 표시 의무 (publisher.py 내장)
- `loc-news` 저장소에 `api_keys.json` 절대 커밋 금지

### Review Engine (E22) — 발행 흐름
```
run_pipeline.py → L0 검사 6종 → review/queue/ 저장
→ approve.py --list   # 대기 확인
→ approve.py --all    # 전체 승인·발행
→ approve.py --only 005930  # 선택 승인
→ approve.py --reject 035720 --reason "사유"  # 거부
```

### L0 자동 차단 6종
1. 면책조항 ("투자 권유가 아니며") — 하드 차단
2. 금지어 없음 (매수 추천·목표가 등) — 하드 차단
3. 고지문구 (쿠팡 링크 있을 때만)
4. AI 표시 ("자동화 시스템" 등)
5. 수치 ETL 대조 — 소프트 경고
6. 쿠팡 링크 유효성 (링크 있을 때만)

### 금지어 목록 위치
`D:\loc_automation\policies\compliance.md`

### GitHub Pages URL
`https://johnpark236-tech.github.io/loc-news/`

---

## 🖥️ 로컬 개발 서버

`file://` 직접 열기 시 fetch CORS 실패. 반드시 아래로 접속:
```bash
python -m http.server 8000
# → http://localhost:8000/chart_viewer_A.html
```
