/* util.js — أدوات مساعدة: أرقام عربية، مراجع، تهريب النص، الحالة في الرابط */

/* الأرقام العربية-الهندية (المشرقية) كما تُكتب في المصحف */
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';
function ar(n) {
  return String(n).replace(/[0-9]/g, d => AR_DIGITS[+d]);
}
/* فصل الآلاف بالفاصلة العربية */
function num(n) {
  if (n === null || n === undefined) return '—';
  return ar(Number(n).toLocaleString('en-US'));
}
function pct(x, digits = 2) {
  if (x === null || x === undefined) return '—';
  return ar(Number(x).toFixed(digits)) + '٪';
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function refLabel(suraName, num, sura) {
  return `سورة ${suraName} · الآية ${ar(num)}`;
}
function qs(name, params) { return params.get(name); }
function debounce(fn, ms = 220) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
function h(strings, ...vals) { return strings.reduce((acc, s, i) => acc + s + (vals[i] ?? ''), ''); }
/* تنزيل ملف نصي */
function download(name, text) {
  const b = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

/* الحالة في الرابط (hash) — ليكون البحث قابلاً للمشاركة */
const State = {
  read() {
    const h = location.hash.replace(/^#\/?/, '');
    const [path, qsStr] = h.split('?');
    const parts = path.split('/').filter(Boolean);
    return { parts, params: new URLSearchParams(qsStr || '') };
  },
  write(parts, params) {
    const p = new URLSearchParams(params || {});
    const qs = p.toString();
    const hash = '#/' + parts.join('/') + (qs ? '?' + qs : '');
    if (hash !== location.hash) history.pushState(null, '', hash);
  },
  replace(parts, params) {
    const p = new URLSearchParams(params || {});
    const qs = p.toString();
    location.replace('#' + '/' + parts.join('/') + (qs ? '?' + qs : ''));
  },
};

/* تلميح عائم */
const Tip = {
  node: null,
  init() { this.node = document.getElementById('tip'); },
  /* ملاحظة أمنية: كل نص قادم من الخادم يمرّ عبر esc() قبل بناء HTML هنا،
     ولا يُدرج أي مدخل مستخدم خام. */
  show(html, x, y) {
    if (!this.node) return;
    this.node.innerHTML = html;
    this.node.classList.add('on');
    const r = this.node.getBoundingClientRect();
    let left = x - r.width / 2, top = y - r.height - 14;
    left = Math.max(8, Math.min(window.innerWidth - r.width - 8, left));
    top = Math.max(8, top);
    this.node.style.left = left + 'px';
    this.node.style.top = top + 'px';
  },
  hide() { if (this.node) this.node.classList.remove('on'); },
};
