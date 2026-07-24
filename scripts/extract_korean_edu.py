"""
Korean Education Knowledge Engine — ETL 스크립트
교재 8권 → 주차·차시 단위 분리 → 정규화 JSON + Markdown 저장
출처: data/education/korean/normalized/, markdown/

절대 규칙:
  - 교재 원문(raw) 외부 공개 금지
  - 메타데이터만 추출·정규화 (Level 2)
  - 출처는 항상 기록
"""

import re
import json
import os
import sys
from pathlib import Path
from datetime import date

try:
    import pdfplumber
    PDF_ENGINE = "pdfplumber"
except ImportError:
    try:
        import pypdf
        PDF_ENGINE = "pypdf"
    except ImportError:
        PDF_ENGINE = None

SOURCE_DIR = Path("D:/logofchoices")
OUTPUT_DIR = Path("D:/logofchoices/data/education/korean")
TODAY = date.today().isoformat()

TEXTBOOKS = [
    {"id": "SEM", "title": "한국어의미론",      "file": "_교재_한국어의미론_v2_1_260522_.pdf",                       "professor": "김해미",  "type": "전공선택"},
    {"id": "PHO", "title": "한국어발음교육론",   "file": "_교재__외국어로서의한국어발음교육론_v3_2_260303_.pdf",       "professor": "손상미",  "type": "전공선택"},
    {"id": "MAT", "title": "한국어교재론",       "file": "_교재__외국어로서의한국어교재론.pdf",                        "professor": "오민수",  "type": "전공필수"},
    {"id": "THE", "title": "언어교수이론",       "file": "_교재_외국어로서의언어교수이론_v2_0_251010_.pdf",            "professor": "",        "type": "전공필수"},
    {"id": "GRM", "title": "한국어문법교육론",   "file": "_교재_외국어로서의한국어문법교육론.pdf",                     "professor": "",        "type": "전공필수"},
    {"id": "REC", "title": "한국어이해교육론",   "file": "_교재__외국어로서의한국어이해교육론.pdf",                    "professor": "권화숙",  "type": "전공필수"},
    {"id": "EXP", "title": "한국어표현교육론",   "file": "_교재_외국어로서한국어표현교육론_260108_.pdf",               "professor": "",        "type": "전공필수"},
    {"id": "VOC", "title": "한국어어휘교육론",   "file": "_교재__외국어로서의한국어어휘교육론.pdf",                    "professor": "오민수",  "type": "전공선택"},
]

TEACHING_METHODS = [
    "역할극", "짝 활동", "토론", "그림 제시", "맥락 제시",
    "게임", "노래", "비교", "대조", "귀납", "연역", "질문법",
    "총체적 신체반응", "청각구두", "직접 교수", "의사소통",
    "과제중심", "내용중심", "암시교수", "협동학습", "자기주도",
]

# ── PDF 텍스트 읽기 ───────────────────────────────────────────────

def read_pdf_pdfplumber(filepath: Path) -> str:
    import pdfplumber
    pages = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)

def read_pdf_pypdf(filepath: Path) -> str:
    import pypdf
    reader = pypdf.PdfReader(str(filepath))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)

def read_textbook(filepath: Path) -> str:
    if PDF_ENGINE == "pdfplumber":
        return read_pdf_pdfplumber(filepath)
    elif PDF_ENGINE == "pypdf":
        return read_pdf_pypdf(filepath)
    else:
        # fallback: raw binary → utf-8
        with open(filepath, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')

# ── 차시 분리 ────────────────────────────────────────────────────

WEEK_PATTERNS = [
    re.compile(r'(\d+)\s*주차\s*(\d+)\s*차시\s*[:\s·]\s*(.{2,40})'),  # N주차 N차시 제목
    re.compile(r'제\s*(\d+)\s*차시\s*[:\s·]\s*(.{2,40})'),             # 제N차시 제목
    re.compile(r'(\d+)\s*주차\s*[:\s·]\s*(.{2,40})'),                  # N주차 제목 (차시 없음)
    re.compile(r'Unit\s*(\d+)\s*[:\s·]\s*(.{2,40})', re.I),           # Unit N
    re.compile(r'Chapter\s*(\d+)\s*[:\s·]\s*(.{2,40})', re.I),        # Chapter N
]

def extract_units(raw_text: str, book_id: str) -> list:
    units = []
    # 텍스트를 줄 단위로 읽으며 차시 헤더 감지
    lines = raw_text.split('\n')
    current = None
    buf = []

    for line in lines:
        line = line.strip()
        matched = False
        for pat in WEEK_PATTERNS:
            m = pat.search(line)
            if m:
                # 이전 차시 저장
                if current:
                    current['raw_text'] = '\n'.join(buf)
                    _enrich_unit(current)
                    units.append(current)
                    buf = []

                groups = m.groups()
                if len(groups) == 3:
                    week, chasi, title = int(groups[0]), int(groups[1]), groups[2].strip()
                elif len(groups) == 2:
                    week, chasi, title = int(groups[0]), 1, groups[1].strip()
                else:
                    week, chasi, title = 1, len(units) + 1, groups[0].strip()

                current = {
                    "id": f"{book_id}_{week:02d}{chasi:02d}",
                    "book_id": book_id,
                    "week": week,
                    "chasi": chasi,
                    "title": title[:40],
                    "learning_goals": [],
                    "key_concepts": [],
                    "examples": [],
                    "teaching_hints": [],
                }
                matched = True
                break

        if not matched and current:
            buf.append(line)

    # 마지막 차시 저장
    if current:
        current['raw_text'] = '\n'.join(buf)
        _enrich_unit(current)
        units.append(current)

    return units

def _enrich_unit(unit: dict):
    text = unit.pop('raw_text', '')
    unit['learning_goals'] = extract_learning_goals(text)
    unit['key_concepts']   = extract_concepts(text)
    unit['examples']       = extract_examples(text)
    unit['teaching_hints'] = extract_teaching_hints(text)

# ── 세부 추출 ────────────────────────────────────────────────────

GOAL_PATTERNS = [
    re.compile(r'학습\s*목표\s*[:\s](.{5,80})'),
    re.compile(r'목표\s*[:\s](.{5,80})'),
    re.compile(r'[①②③④⑤](.{5,60})'),
]
CONCEPT_PATTERNS = [
    re.compile(r'([가-힣a-zA-Z ]{2,12})\s*[이란은는]\s+(.{10,80})'),
    re.compile(r'([가-힣a-zA-Z ]{2,12})\s*[:：]\s+(.{10,80})'),
]
EXAMPLE_PATTERNS = [
    re.compile(r'예\)\s*(.{3,80})'),
    re.compile(r'예시\s*[:\s]\s*(.{3,80})'),
    re.compile(r'[【\[]예[】\]]\s*(.{3,80})'),
]

def extract_learning_goals(text: str) -> list:
    goals = []
    for pat in GOAL_PATTERNS:
        for m in pat.finditer(text):
            g = m.group(1).strip()[:80]
            if g and g not in goals:
                goals.append(g)
    return goals[:5]

def extract_concepts(text: str) -> list:
    concepts = []
    seen = set()
    for pat in CONCEPT_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).strip()
            defn = m.group(2).strip()[:120]
            if name not in seen and len(name) >= 2:
                seen.add(name)
                concepts.append({"name": name, "definition": defn})
    return concepts[:10]

def extract_examples(text: str) -> list:
    examples = []
    for pat in EXAMPLE_PATTERNS:
        for m in pat.finditer(text):
            ex = m.group(1).strip()[:100]
            if ex and ex not in examples:
                examples.append(ex)
    return examples[:8]

def extract_teaching_hints(text: str) -> list:
    return [m for m in TEACHING_METHODS if m in text]

# ── 저장 ─────────────────────────────────────────────────────────

def save_unit_markdown(unit: dict, book_title: str):
    filename = f"{unit['id']}_{unit['title'][:20]}.md"
    content = f"""# {unit['title']}
## 기본 정보
- **교재**: {book_title}
- **주차**: {unit['week']}주차 {unit['chasi']}차시
- **ID**: {unit['id']}

## 학습목표
{chr(10).join(f'- {g}' for g in unit.get('learning_goals', [])) or '- (미추출)'}

## 핵심개념
{chr(10).join(f"- **{c['name']}**: {c['definition']}" for c in unit.get('key_concepts', [])) or '- (미추출)'}

## 예시
{chr(10).join(f'- {e}' for e in unit.get('examples', [])) or '- (미추출)'}

## 교수법 힌트
{chr(10).join(f'- {m}' for m in unit.get('teaching_hints', [])) or '- (미추출)'}

## 출처
- {book_title} {unit['week']}주차 {unit['chasi']}차시
"""
    path = OUTPUT_DIR / "markdown" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def save_raw_text(book_id: str, text: str):
    path = OUTPUT_DIR / "raw" / f"{book_id}_raw.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

# ── 메인 ─────────────────────────────────────────────────────────

def main():
    if PDF_ENGINE is None:
        print("[WARNING]  PDF 라이브러리 없음. 설치: pip install pdfplumber")
        print("   텍스트 파일(.txt)도 지원합니다.")

    all_units = []
    results = []

    for book in TEXTBOOKS:
        filepath = SOURCE_DIR / book['file']
        # PDF 없으면 같은 이름 txt fallback
        if not filepath.exists():
            txt_path = filepath.with_suffix('.txt')
            if txt_path.exists():
                filepath = txt_path
            else:
                print(f"[WARNING]  파일 없음: {book['file']}")
                results.append({"book": book['title'], "units": 0, "status": "파일없음"})
                continue

        print(f"[BOOK] 처리 중: {book['title']} ({filepath.name})")
        raw = read_textbook(filepath)

        save_raw_text(book['id'], raw)

        units = extract_units(raw, book['id'])
        print(f"   차시 {len(units)}개 추출")

        for unit in units:
            save_unit_markdown(unit, book['title'])

        all_units.extend(units)
        results.append({"book": book['title'], "units": len(units), "status": "완료"})

        out_path = OUTPUT_DIR / "normalized" / f"{book['id']}_units.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                "meta": {
                    "book_id":    book['id'],
                    "title":      book['title'],
                    "professor":  book['professor'],
                    "type":       book['type'],
                    "total_units": len(units),
                    "extracted":  TODAY,
                    "data_type":  "메타데이터 — 내부 연구용",
                },
                "units": units
            }, f, ensure_ascii=False, indent=2)

    index_path = OUTPUT_DIR / "normalized" / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({
            "total_books":  len(TEXTBOOKS),
            "total_units":  len(all_units),
            "books":        [{"id": b['id'], "title": b['title'], "type": b['type']} for b in TEXTBOOKS],
            "updated":      TODAY,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'─'*50}")
    print(f"[OK] 완료: 총 {len(all_units)}차시 추출")
    for r in results:
        status = "[OK]" if r['status'] == "완료" else "[WARNING] "
        print(f"  {status} {r['book']}: {r['units']}차시")

if __name__ == "__main__":
    main()
