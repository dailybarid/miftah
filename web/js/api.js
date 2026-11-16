/* api.js — طبقة الاتصال بالواجهة الخلفية */
const API = (() => {
  const base = '/api';
  async function get(path, params) {
    const url = new URL(base + path, location.origin);
    if (params) for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue;
      url.searchParams.set(k, v);
    }
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!r.ok) {
      let msg = 'خطأ في الاتصال';
      try { const j = await r.json(); msg = j.detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    return r.json();
  }
  return {
    meta: () => get('/meta'),
    suras: () => get('/suras'),
    sura: (n, words) => get(`/sura/${n}`, words ? { words: 1 } : undefined),
    ayah: (s, a) => get(`/ayah/${s}/${a}`),
    word: (id) => get(`/word/${id}`),
    search: (p) => get('/search', p),
    suggest: (q) => get('/suggest', { q }),
    tag: (w) => get('/tag', { w }),
    pos: () => get('/pos'),
    posSearch: (p) => get('/pos/search', p),
    roots: (p) => get('/roots', p),
    root: (id) => get(`/root/${id}`),
    lemma: (id) => get(`/lemma/${id}`),
    compare: (w1, w2) => get('/compare', { w1, w2 }),
    stats: () => get('/stats'),
    letters: (p) => get('/stats/letters', p),
    ayahLetters: (s, a) => get(`/stats/ayah-letters/${s}/${a}`),
    withoutLetter: (letter) => get('/stats/without-letter', { letter }),
    analysis: (s, a) => get(`/stats/analysis/${s}/${a}`),
    graphRoots: (p) => get('/graph/roots', p),
    mindmap: (p) => get('/graph/mindmap', p),
    graphAyah: (s, a) => get(`/graph/ayah/${s}/${a}`),
    graphWord: (w, p) => get('/graph/word', Object.assign({ w }, p || {})),
    topics: () => get('/topics'),
    random: () => get('/random'),
  };
})();
