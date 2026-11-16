/* app.js — الموجّه (router) وربط الأحداث */

const App = {
  main: null,
  current: { view: 'home', params: new URLSearchParams() },

  init() {
    this.main = document.getElementById('main');
    Tip.init();
    document.getElementById('theme').onclick = () => this.toggleTheme();
    document.getElementById('go').onclick = () => this.submitSearch();
    const q = document.getElementById('q');
    q.addEventListener('keydown', e => { if (e.key === 'Enter') { this.submitSearch(); } });
    q.addEventListener('input', debounce(() => this.suggest(), 200));
    document.addEventListener('click', e => { if (!e.target.closest('.searchbar')) this.hideSuggest(); });

    document.querySelectorAll('nav.tabs button').forEach(b => b.onclick = () => {
      const v = b.dataset.nav;
      location.hash = v === 'home' ? '#/' : '#/' + v;
    });
    document.querySelector('.brand').onclick = () => location.hash = '#/';

    // تفويض الأحداث لكل الأزرار والروابط الديناميكية
    document.body.addEventListener('click', e => this.delegate(e));
    document.body.addEventListener('mousemove', e => {
      const w = e.target.closest('[data-word]');
      if (!w) { Tip.hide(); return; }
      Tip.show(`<b>${esc(w.textContent.trim())}</b><br>اضغط لعرض الحرف والحركات والجذر والموضع`, e.clientX, e.clientY);
    });

    window.addEventListener('popstate', () => this.route());
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
        e.preventDefault(); document.getElementById('q').focus(); this.hideSuggest();
      }
      if (e.key === 'Escape') this.hideSuggest();
      if (e.key === 'ت' && e.ctrlKey) { }
    });
    this.restoreTheme();
    this.route();
  },

  /* ------------------------------- التنقّل ------------------------------- */
  async route() {
    const { parts, params } = State.read();
    const head = parts[0] || 'home';
    this.current = { view: head, params };
    document.querySelectorAll('nav.tabs button').forEach(b =>
      b.classList.toggle('active', b.dataset.nav === (head === '' ? 'home' : head) ||
        (head === 'ayah' && b.dataset.nav === 'mushaf') ||
        (head === 'sura' && b.dataset.nav === 'mushaf') ||
        (head === 'tag' && b.dataset.nav === 'search') ||
        (head === 'root' && b.dataset.nav === 'graph') ||
        (head === 'word' && b.dataset.nav === 'search')));
    window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
    const qBox = document.getElementById('q');
    if (params.get('q') !== null && qBox.value !== params.get('q')) qBox.value = params.get('q');
    try {
      switch (head) {
        case 'home': await V.home(this.main); break;
        case 'search': await V.results(this.main, params); break;
        case 'ayah': await V.ayah(this.main, +parts[1], +parts[2]); break;
        case 'word': await V.word(this.main, +parts[1]); break;
        case 'tag': await V.tag(this.main, decodeURIComponent(parts[1] || '')); break;
        case 'root': await V.rootById(this.main, +parts[1]); break;
        case 'roots': await V.rootList(this.main, (await API.roots({ limit: 120, sort: 'count' })).roots); break;
        case 'sura': await V.sura(this.main, +parts[1]); break;
        case 'pos': await V.pos(this.main, parts[1]); break;
        case 'mushaf': await V.mushaf(this.main, params); break;
        case 'stats': await V.stats(this.main); break;
        case 'graph': await V.graph(this.main, params); break;
        case 'mindmap': await V.mindmap(this.main, params); break;
        case 'about': await V.about(this.main); break;
        default: await V.home(this.main);
      }
    } catch (err) {
      this.main.innerHTML = `<div class="card"><h2>تعذّر العرض</h2><p>${esc(err.message)}</p>
        <button class="chip" onclick="location.hash='#/'">عودة إلى الرئيسية</button></div>`;
    }
  },

  go(parts, params) {
    State.write(Array.isArray(parts) ? parts : [parts], params);
    this.route();
  },

  submitSearch() {
    const q = document.getElementById('q').value.trim();
    this.hideSuggest();
    if (!q) return;
    const m = q.replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d)).match(/^(\d{1,3})\s*[:/.]\s*(\d{1,3})$/);
    if (m) return this.go(['ayah', m[1], m[2]]);
    if (/^جذر:|^root:/.test(q)) {
      const term = q.split(':')[1].trim();
      return API.roots({ q: term, limit: 1 }).then(r => {
        if (r.roots.length) this.go(['root', r.roots[0].id]);
        else this.go(['search'], { q });
      });
    }
    this.go(['search'], { q });
  },

  /* ------------------------------- الإكمال التلقائي ------------------------------- */
  async suggest() {
    const box = document.getElementById('suggest');
    const q = document.getElementById('q').value.trim();
    if (q.length < 2) return this.hideSuggest();
    try {
      const { items } = await API.suggest(q);
      if (!items.length) return this.hideSuggest();
      box.innerHTML = items.map(it => `<div class="it" data-quick="${esc(it.text)}">
        <span class="t">${esc(it.display)}</span>
        <span class="c">${num(it.count)} موضعاً · ${ar(it.suras)} سورة</span></div>`).join('');
      box.hidden = false;
    } catch (e) { this.hideSuggest(); }
  },
  hideSuggest() { const b = document.getElementById('suggest'); if (b) { b.hidden = true; b.innerHTML = ''; } },

  /* ------------------------------- تفويض الأزرار ------------------------------- */
  delegate(e) {
    const t = e.target.closest('[data-goto],[data-quick],[data-wordid],[data-tag],[data-root],[data-copy],[data-audio],[data-print],[data-page],[data-share],[data-graph-ayah],[data-graph-sura],[data-prev],[data-next],[data-word="w"],[data-nav]');
    if (!t) return;

    if (t.dataset.word === 'w') {
      e.preventDefault();
      if (t.dataset.id) return this.go(['word', t.dataset.id]);
      // من صفحة نتائج البحث: نبحث عن رقم الكلمة في الآية عبر صفحة الآية
      const [s, a] = (t.dataset.ref || '').split(':');
      const n = +t.dataset.n;
      if (s && a && n) return this.go(['ayah', s, a], { w: n });
      return;
    }
    if (t.dataset.nav) return this.go(t.dataset.nav === 'home' ? ['home'] : [t.dataset.nav]);
    if (t.dataset.quick) { document.getElementById('q').value = t.dataset.quick; return this.submitSearch(); }
    if (t.dataset.goto) {
      const g = t.dataset.goto;
      if (g.startsWith('sura/')) return this.go(['sura', g.split('/')[1]]);
      if (g.startsWith('pos:')) return this.go(['pos', g.slice(4)]);
      const [s, a] = g.split('/');
      return this.go(['ayah', s, a]);
    }
    if (t.dataset.wordid) return this.go(['word', t.dataset.wordid]);
    if (t.dataset.tag) return this.go(['tag', encodeURIComponent(t.dataset.tag)]);
    if (t.dataset.root) return this.go(['root', t.dataset.root]);
    if (t.dataset.graphAyah) { const [s, a] = t.dataset.graphAyah.split('/'); return this.go(['ayah', s, a]); }
    if (t.dataset.graphSura) return this.go(['graph'], { sura: t.dataset.graphSura, minw: 4 });
    if (t.dataset.prev && t.dataset.prev !== '/') { const [s, a] = t.dataset.prev.split('/'); return this.go(['ayah', s, a]); }
    if (t.dataset.next && t.dataset.next !== '/') { const [s, a] = t.dataset.next.split('/'); return this.go(['ayah', s, a]); }
    if (t.dataset.page) {
      const p = new URLSearchParams(this.current.params);
      const limit = +(p.get('limit') || 25);
      p.set('offset', (+t.dataset.page - 1) * limit);
      return this.go(['search'], Object.fromEntries(p));
    }
    if (t.dataset.share) {
      const ref = (t.closest('[data-ayah]') || {}).dataset?.ayah;
      const url = location.href;
      if (navigator.clipboard) navigator.clipboard.writeText(url);
      Tip.show('تم نسخ الرابط' + (ref ? ` — ${esc(ref)}` : ''), e.clientX, e.clientY);
      setTimeout(() => Tip.hide(), 1400);
      return;
    }
    if (t.dataset.copy) {
      const ref = t.dataset.copyRef || '';
      const text = `${t.dataset.copy}\n\n[${ref}] — محرك مفتاح للبحث في القرآن الكريم`;
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(() =>
        Tip.show('تم نسخ الآية', e.clientX, e.clientY));
      setTimeout(() => Tip.hide(), 1400);
      return;
    }
    if (t.dataset.print) { window.print(); return; }
    if (t.dataset.audio) return this.audio(t.dataset.audio, e.clientX, e.clientY);
    // خيارات البحث
    if (t.id === 'apply') return this.applyOptions();
    if (t.id === 'reset') return this.go(['search'], { q: this.current.params.get('q') || '' });
  },

  applyOptions() {
    const v = id => (document.getElementById(id) || {}).value;
    const c = id => (document.getElementById(id) || {}).checked;
    const p = {
      q: this.current.params.get('q') || '',
      mode: v('opt-mode'), limit: this.current.params.get('limit') || 25, offset: 0,
      tashkeel: c('opt-tashkeel') ? 1 : '',
      it: c('opt-it') ? 1 : 0, ua: c('opt-ua') ? 1 : 0, uy: c('opt-uy') ? 1 : 0,
      ut: c('opt-ut') ? 1 : 0, ih: c('opt-ih') ? 1 : 0,
      sura: v('f-sura'), juz: v('f-juz'), pmin: v('f-pmin'), pmax: v('f-pmax'),
      rev: v('f-rev'), wmin: v('f-wmin'), wmax: v('f-wmax'),
      sajda: c('f-sajda') ? 1 : '',
    };
    this.go(['search'], p);
  },

  /* ------------------------------- التلاوة ------------------------------- */
  audio(ref, x, y) {
    const [s, a] = ref.split(':').map(Number);
    const pad = (n, w = 3) => String(n).padStart(w, '0');
    const file = `${pad(s)}${pad(a)}.mp3`;
    let box = document.getElementById('audioBox');
    if (!box) {
      box = document.createElement('div');
      box.id = 'audioBox';
      box.className = 'card';
      box.style.cssText = 'position:fixed;bottom:18px;inset-inline-start:18px;z-index:80;max-width:420px';
      document.body.appendChild(box);
    }
    const rec = localStorage.getItem('reciter') || RECITERS[0][0];
    box.innerHTML = `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <strong>تلاوة ${ar(s)}:${ar(a)}</strong>
      <select id="rec">${RECITERS.map(([v, t]) => `<option value="${v}" ${v === rec ? 'selected' : ''}>${t}</option>`).join('')}</select>
      <button class="chip" id="closeAudio">إغلاق</button></div>
      <audio id="au" controls autoplay style="width:100%;margin-top:8px"
        src="https://everyayah.com/data/${rec}/${file}"></audio>
      <div class="note" style="margin-top:6px;font-size:12.5px">التلاوة تُحمَّل من everyayah.com مباشرة.</div>`;
    box.querySelector('#rec').onchange = e => {
      localStorage.setItem('reciter', e.target.value);
      box.querySelector('#au').src = `https://everyayah.com/data/${e.target.value}/${file}`;
      box.querySelector('#au').play();
    };
    box.querySelector('#closeAudio').onclick = () => box.remove();
  },

  /* ------------------------------- السمة ------------------------------- */
  toggleTheme() {
    const cur = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = cur;
    localStorage.setItem('theme', cur);
  },
  restoreTheme() {
    const t = localStorage.getItem('theme');
    if (t) document.documentElement.dataset.theme = t;
    else if (window.matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = 'dark';
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
