/**
 * Korean Education Knowledge Engine API
 * Module: Education (v6.0 헌법)
 * 브라우저 정적 JSON 기반 — 원문 미포함, 메타데이터만 제공
 */

const KOREAN_EDU = (() => {

  const BASE = './data/education/korean/normalized/';
  let _index = null;
  const _books = {};

  async function init() {
    if (_index) return _index;
    const res = await fetch(BASE + 'index.json');
    if (!res.ok) throw new Error('index.json 로드 실패');
    _index = await res.json();
    return _index;
  }

  async function getBooks() {
    if (!_index) await init();
    return _index.books;
  }

  async function getStats() {
    if (!_index) await init();
    return {
      total_books:    _index.total_books,
      total_units:    _index.total_units,
      total_concepts: _index.total_concepts,
      updated:        _index.created,
    };
  }

  async function loadBook(bookId) {
    if (_books[bookId]) return _books[bookId];
    const res = await fetch(BASE + bookId + '_units.json');
    if (!res.ok) throw new Error(`${bookId} 로드 실패`);
    _books[bookId] = await res.json();
    return _books[bookId];
  }

  async function loadAllBooks() {
    if (!_index) await init();
    await Promise.all(_index.books.map(b => loadBook(b.id)));
  }

  function _methods(unit) {
    return unit.teaching_methods || unit.teaching_hints || [];
  }

  async function searchConcept(keyword) {
    if (!_index) await init();
    const kw = keyword.trim().toLowerCase();
    if (!kw) return [];
    const results = [];
    for (const book of _index.books) {
      const data = await loadBook(book.id);
      for (const unit of (data.units || [])) {
        for (const c of (unit.key_concepts || [])) {
          if (c.name.includes(kw) || (c.definition || '').toLowerCase().includes(kw)) {
            results.push({
              book_id:        book.id,
              book_title:     book.title,
              unit_id:        unit.id,
              week:           unit.week,
              chasi:          unit.chasi,
              unit_title:     unit.title,
              concept:        c,
              teaching_hints: _methods(unit),
              examples:       unit.examples || [],
              learning_goals: unit.learning_goals || [],
            });
          }
        }
      }
    }
    return results;
  }

  async function searchByMethod(method) {
    if (!_index) await init();
    const results = [];
    for (const book of _index.books) {
      const data = await loadBook(book.id);
      for (const unit of (data.units || [])) {
        if (_methods(unit).includes(method)) {
          results.push({
            book_id:    book.id,
            book_title: book.title,
            unit_id:    unit.id,
            week:       unit.week,
            chasi:      unit.chasi,
            unit_title: unit.title,
            key_concepts: unit.key_concepts || [],
          });
        }
      }
    }
    return results;
  }

  async function getBookUnits(bookId) {
    const data = await loadBook(bookId);
    return data.units || [];
  }

  const METHODS = [
    "역할극","짝 활동","토론","그림 제시","맥락 제시",
    "게임","노래","비교","대조","귀납","연역","질문법",
    "총체적 신체반응","청각구두","직접 교수","의사소통",
    "과제중심","내용중심","암시교수","협동학습","자기주도",
  ];

  async function getMethodsWithCount() {
    await loadAllBooks();
    return METHODS.map(m => {
      let count = 0;
      for (const data of Object.values(_books)) {
        for (const unit of (data.units || [])) {
          if (_methods(unit).includes(m)) count++;
        }
      }
      return { name: m, count };
    }).filter(m => m.count > 0).sort((a, b) => b.count - a.count);
  }

  return {
    init, getBooks, getStats,
    loadBook, loadAllBooks,
    searchConcept, searchByMethod,
    getBookUnits, getMethodsWithCount,
  };
})();
