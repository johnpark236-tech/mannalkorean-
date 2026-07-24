"""
Korean Education Knowledge Engine — AI 교안 생성 엔진
Knowledge DB 기반 → Claude API → 새로운 교안 생성 (Level 3)

절대 규칙:
  - 교재 원문 복사 금지
  - 교육 원리 기반 완전히 새로 작성
  - 출처 항상 기록
"""

import argparse
import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path

DB_PATH = Path("D:/logofchoices/data/education/korean/db/korean_edu.db")
TODAY   = date.today().isoformat()

# ── DB 조회 헬퍼 ─────────────────────────────────────────────────

def _connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB 없음: {DB_PATH}\n먼저 build_korean_edu_db.py 를 실행하세요.")
    return sqlite3.connect(DB_PATH)

def get_concepts_by_name(keyword: str) -> list:
    con = _connect()
    rows = con.execute(
        "SELECT concept_id, name, definition FROM concepts WHERE name LIKE ? LIMIT 10",
        (f"%{keyword}%",)
    ).fetchall()
    con.close()
    return [{"id": r[0], "name": r[1], "definition": r[2]} for r in rows]

def get_concepts_from_db(concept_ids: list) -> list:
    con = _connect()
    placeholders = ",".join("?" * len(concept_ids))
    rows = con.execute(
        f"SELECT concept_id, name, definition FROM concepts WHERE concept_id IN ({placeholders})",
        concept_ids
    ).fetchall()
    con.close()
    return [{"id": r[0], "name": r[1], "definition": r[2]} for r in rows]

def get_teaching_methods(concept_ids: list) -> list:
    if not concept_ids:
        return []
    con = _connect()
    placeholders = ",".join("?" * len(concept_ids))
    rows = con.execute(
        f"""SELECT DISTINCT tm.name, tm.description, tm.theory_base
            FROM teaching_methods tm
            JOIN concept_methods cm ON tm.method_id = cm.method_id
            WHERE cm.concept_id IN ({placeholders})""",
        concept_ids
    ).fetchall()
    con.close()
    return [{"name": r[0], "description": r[1], "theory_base": r[2]} for r in rows]

def get_concept_sources(concept_ids: list) -> list:
    if not concept_ids:
        return []
    con = _connect()
    placeholders = ",".join("?" * len(concept_ids))
    rows = con.execute(
        f"""SELECT DISTINCT b.title, u.week, u.chasi
            FROM concept_sources cs
            JOIN books b ON cs.book_id = b.book_id
            JOIN units u ON cs.unit_id = u.unit_id
            WHERE cs.concept_id IN ({placeholders})""",
        concept_ids
    ).fetchall()
    con.close()
    return [f"{r[0]} {r[1]}주차 {r[2]}차시" for r in rows]

def save_lesson_plan(plan: dict, profile: dict, concept_ids: list, model: str):
    con = _connect()
    plan_id = f"PLAN_{uuid.uuid4().hex[:8].upper()}"
    profile_id = f"PROF_{uuid.uuid4().hex[:8].upper()}"
    con.execute(
        "INSERT OR REPLACE INTO student_profiles (profile_id, country, age_group, topik_level, goal, class_size, class_time) VALUES (?,?,?,?,?,?,?)",
        (profile_id, profile['country'], profile['age_group'], profile['topik_level'],
         profile['focus'], profile['class_size'], profile['class_time'])
    )
    con.execute(
        "INSERT INTO lesson_plans (plan_id, profile_id, concept_ids, content, ai_model, created_at) VALUES (?,?,?,?,?,?)",
        (plan_id, profile_id, json.dumps(concept_ids, ensure_ascii=False),
         json.dumps(plan, ensure_ascii=False), model, TODAY)
    )
    con.commit(); con.close()
    return plan_id

# ── 교안 생성 ────────────────────────────────────────────────────

def generate_lesson_plan(
    country: str,
    age_group: str,
    topik_level: int,
    class_size: int,
    class_time: int,
    focus: str,
    concept_keyword: str,
    concept_ids: list = None,
    model: str = "claude-sonnet-4-6",
) -> dict:

    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic 패키지가 없습니다. pip install anthropic")

    # 개념 조회
    if concept_ids:
        concepts = get_concepts_from_db(concept_ids)
    else:
        concepts = get_concepts_by_name(concept_keyword)
        concept_ids = [c['id'] for c in concepts]

    if not concepts:
        concepts = [{"name": concept_keyword, "definition": "(DB 미등록 — 키워드 기반 생성)"}]

    methods  = get_teaching_methods(concept_ids)
    sources  = get_concept_sources(concept_ids)

    profile = {
        "country": country, "age_group": age_group, "topik_level": topik_level,
        "class_size": class_size, "class_time": class_time, "focus": focus,
    }

    prompt = f"""당신은 한국어 교육 전문가입니다.
아래 정보를 바탕으로 최적의 수업 교안을 JSON으로 작성하세요.

## 학생 정보
- 국적: {country}
- 연령: {age_group}
- TOPIK 수준: {topik_level}급
- 인원: {class_size}명
- 수업 시간: {class_time}분
- 수업 목표: {focus} 중심

## 학습 개념
{json.dumps(concepts, ensure_ascii=False, indent=2)}

## 추천 교수법
{json.dumps(methods, ensure_ascii=False, indent=2) if methods else "- (DB 교수법 미매칭 — 일반 원칙 적용)"}

## 참고 출처 (교재)
{chr(10).join(f'- {s}' for s in sources) if sources else "- (출처 없음 — 일반 교육 원리 적용)"}

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)
{{
  "학습목표": ["목표1", "목표2"],
  "도입": {{"시간": "N분", "활동": "...", "교사멘트": "..."}},
  "전개": [
    {{"순서": 1, "시간": "N분", "활동": "...", "설명": "..."}},
    {{"순서": 2, "시간": "N분", "활동": "...", "설명": "..."}}
  ],
  "정리": {{"시간": "N분", "활동": "..."}},
  "평가": {{"방법": "...", "기준": "..."}},
  "숙제": "...",
  "주의사항": ["{country} 학습자 주의점"],
  "참고자료": {json.dumps(sources or [], ensure_ascii=False)}
}}

중요: 교재 원문을 그대로 복사하지 마세요.
교육 원리를 바탕으로 완전히 새로운 교안을 작성하세요."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    # JSON 파싱
    try:
        lesson_plan = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        lesson_plan = json.loads(m.group()) if m else {"raw": raw}

    plan_id = save_lesson_plan(lesson_plan, profile, concept_ids, model)
    lesson_plan['_plan_id'] = plan_id
    lesson_plan['_sources'] = sources

    return lesson_plan

# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI 한국어 교안 생성기")
    parser.add_argument("--country",  default="베트남",  help="학습자 국적")
    parser.add_argument("--age",      default="20대",    help="연령대")
    parser.add_argument("--topik",    type=int, default=2, help="TOPIK 수준 (1~6)")
    parser.add_argument("--size",     type=int, default=20, help="수업 인원")
    parser.add_argument("--time",     type=int, default=50, help="수업 시간(분)")
    parser.add_argument("--focus",    default="말하기",  help="수업 목표 (말하기/듣기/읽기/쓰기)")
    parser.add_argument("--concept",  default="",        help="학습 개념 키워드")
    parser.add_argument("--model",    default="claude-sonnet-4-6", help="Claude 모델")
    args = parser.parse_args()

    print(f"[NOTE] 교안 생성 중...")
    print(f"   학습자: {args.country} {args.age} TOPIK{args.topik}")
    print(f"   수업: {args.size}명 · {args.time}분 · {args.focus} 중심")
    print(f"   개념: {args.concept or '(미지정)'}")

    plan = generate_lesson_plan(
        country=args.country,
        age_group=args.age,
        topik_level=args.topik,
        class_size=args.size,
        class_time=args.time,
        focus=args.focus,
        concept_keyword=args.concept,
        model=args.model,
    )

    print(f"\n[OK] 교안 생성 완료 (ID: {plan.get('_plan_id','?')})")
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
