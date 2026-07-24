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

## 🖥️ 로컬 개발 서버

`file://` 직접 열기 시 fetch CORS 실패. 반드시 아래로 접속:
```bash
python -m http.server 8000
# → http://localhost:8000/chart_viewer_A.html
```
