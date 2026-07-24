"""
Korean Education Knowledge Engine — SQLite DB 구축
normalized JSON → SQLite DB (data/education/korean/db/korean_edu.db)
"""

import json
import sqlite3
from pathlib import Path
from datetime import date

NORMALIZED_DIR = Path("D:/logofchoices/data/education/korean/normalized")
DB_PATH        = Path("D:/logofchoices/data/education/korean/db/korean_edu.db")
TODAY          = date.today().isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    professor   TEXT,
    type        TEXT,
    total_units INTEGER DEFAULT 0,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS units (
    unit_id     TEXT PRIMARY KEY,
    book_id     TEXT NOT NULL,
    week        INTEGER,
    chasi       INTEGER,
    title       TEXT,
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

CREATE TABLE IF NOT EXISTS learning_goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id     TEXT NOT NULL,
    goal        TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(unit_id)
);

CREATE TABLE IF NOT EXISTS concepts (
    concept_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_en         TEXT,
    definition      TEXT,
    topik_level     TEXT,
    difficulty      TEXT,
    confidence      REAL DEFAULT 0.5,
    human_reviewed  INTEGER DEFAULT 0,
    created_at      TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS concept_sources (
    concept_id  TEXT NOT NULL,
    book_id     TEXT NOT NULL,
    unit_id     TEXT NOT NULL,
    page_hint   TEXT,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
);

CREATE TABLE IF NOT EXISTS examples (
    example_id  TEXT PRIMARY KEY,
    concept_id  TEXT,
    sentence    TEXT,
    meaning     TEXT,
    difficulty  TEXT,
    source      TEXT,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
);

CREATE TABLE IF NOT EXISTS teaching_methods (
    method_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    theory_base TEXT
);

CREATE TABLE IF NOT EXISTS concept_methods (
    concept_id  TEXT NOT NULL,
    method_id   TEXT NOT NULL,
    PRIMARY KEY (concept_id, method_id)
);

CREATE TABLE IF NOT EXISTS error_patterns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id  TEXT,
    country     TEXT,
    pattern     TEXT,
    suggestion  TEXT,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
);

CREATE TABLE IF NOT EXISTS student_profiles (
    profile_id  TEXT PRIMARY KEY,
    country     TEXT,
    age_group   TEXT,
    topik_level INTEGER,
    goal        TEXT,
    class_size  INTEGER,
    class_time  INTEGER
);

CREATE TABLE IF NOT EXISTS lesson_plans (
    plan_id         TEXT PRIMARY KEY,
    profile_id      TEXT,
    concept_ids     TEXT,
    content         TEXT,
    ai_model        TEXT,
    human_reviewed  INTEGER DEFAULT 0,
    created_at      TEXT,
    FOREIGN KEY (profile_id) REFERENCES student_profiles(profile_id)
);

CREATE TABLE IF NOT EXISTS class_results (
    result_id    TEXT PRIMARY KEY,
    plan_id      TEXT,
    satisfaction INTEGER,
    test_score   REAL,
    teacher_note TEXT,
    created_at   TEXT,
    FOREIGN KEY (plan_id) REFERENCES lesson_plans(plan_id)
);
"""

SEED_METHODS = [
    ("MTH_001", "역할극",       "실제 의사소통 상황을 재연하는 활동",          "의사소통 교수법"),
    ("MTH_002", "짝 활동",      "두 학습자가 협력하여 목표어 연습",             "협동학습"),
    ("MTH_003", "토론",         "주제에 대해 논점을 제시하고 반론하는 활동",    "의사소통 교수법"),
    ("MTH_004", "그림 제시",    "시각 자료를 활용한 의미 제시",                 "직접 교수법"),
    ("MTH_005", "맥락 제시",    "실제 사용 맥락을 통한 의미 이해",              "과제중심교수법"),
    ("MTH_006", "게임",         "경쟁·협력 게임을 통한 언어 연습",              "의사소통 교수법"),
    ("MTH_007", "귀납",         "예시 → 규칙 발견 순서의 수업",                 "발견학습"),
    ("MTH_008", "연역",         "규칙 제시 → 예시 적용 순서의 수업",            "직접 교수법"),
    ("MTH_009", "총체적 신체반응", "신체 동작을 통한 언어 학습",                "TPR"),
    ("MTH_010", "청각구두",     "듣기·말하기 반복을 통한 언어 습득",            "청각구두식 교수법"),
    ("MTH_011", "과제중심",     "실제 과제 수행을 통한 언어 사용",              "과제중심교수법"),
    ("MTH_012", "암시교수",     "편안한 환경에서의 무의식적 언어 습득",         "암시교수법"),
    ("MTH_013", "협동학습",     "소그룹 협력을 통한 학습",                      "협동학습"),
    ("MTH_014", "질문법",       "교사의 질문으로 사고를 유도하는 교수법",       "소크라테스식"),
]

def build_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    # 교수법 시드 데이터
    cur.executemany(
        "INSERT OR IGNORE INTO teaching_methods (method_id, name, description, theory_base) VALUES (?,?,?,?)",
        SEED_METHODS
    )

    # normalized JSON → DB
    files = sorted(NORMALIZED_DIR.glob("*_units.json"))
    if not files:
        print("[WARNING]  normalized JSON 없음. 먼저 extract_korean_edu.py 를 실행하세요.")
        con.commit(); con.close(); return

    total_units = 0
    concept_counter = 1

    for jf in files:
        data = json.loads(jf.read_text(encoding='utf-8'))
        meta  = data['meta']
        units = data['units']

        cur.execute(
            "INSERT OR REPLACE INTO books (book_id, title, professor, type, total_units, created_at) VALUES (?,?,?,?,?,?)",
            (meta['book_id'], meta['title'], meta.get('professor',''), meta.get('type',''), len(units), TODAY)
        )

        for unit in units:
            cur.execute(
                "INSERT OR REPLACE INTO units (unit_id, book_id, week, chasi, title) VALUES (?,?,?,?,?)",
                (unit['id'], meta['book_id'], unit.get('week', 0), unit.get('chasi', 0), unit.get('title',''))
            )

            for goal in unit.get('learning_goals', []):
                cur.execute("INSERT INTO learning_goals (unit_id, goal) VALUES (?,?)", (unit['id'], goal))

            for c in unit.get('key_concepts', []):
                cid = f"{meta['book_id']}_CONCEPT_{concept_counter:03d}"
                cur.execute(
                    "INSERT OR IGNORE INTO concepts (concept_id, name, definition, confidence, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (cid, c['name'], c.get('definition',''), 0.5, TODAY, TODAY)
                )
                cur.execute(
                    "INSERT INTO concept_sources (concept_id, book_id, unit_id) VALUES (?,?,?)",
                    (cid, meta['book_id'], unit['id'])
                )
                for hint in unit.get('teaching_hints', []):
                    mid = next((m[0] for m in SEED_METHODS if m[1] == hint), None)
                    if mid:
                        cur.execute("INSERT OR IGNORE INTO concept_methods (concept_id, method_id) VALUES (?,?)", (cid, mid))
                concept_counter += 1

        total_units += len(units)
        print(f"  [OK] {meta['title']}: {len(units)}차시 → DB 입력")

    con.commit()

    # 통계
    tables = ["books","units","concepts","learning_goals","concept_sources","examples","teaching_methods","concept_methods"]
    print(f"\n{'─'*50}")
    print(f"DB: {DB_PATH}")
    for t in tables:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<22}: {cnt:>6}행")

    con.close()
    print(f"\n[OK] DB 구축 완료: 총 {total_units}차시")

if __name__ == "__main__":
    build_db()
