/* charts.js — رسوم SVG بسيطة مبنية باليد (بلا تبعيات) */

const SVGNS = 'http://www.w3.org/2000/svg';
const Chart = {
  _svg(w, h) {
    const s = document.createElementNS(SVGNS, 'svg');
    s.setAttribute('viewBox', `0 0 ${w} ${h}`);
    s.setAttribute('class', 'chart');
    s.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    return s;
  },
  _t(parent, x, y, text, opts = {}) {
    const t = document.createElementNS(SVGNS, 'text');
    t.setAttribute('x', x); t.setAttribute('y', y);
    t.setAttribute('text-anchor', opts.anchor || 'middle');
    if (opts.size) t.setAttribute('font-size', opts.size);
    if (opts.cls) t.setAttribute('class', opts.cls);
    t.textContent = text;
    parent.appendChild(t);
    return t;
  },
  /* أعمدة رأسية */
  bars(container, data, opts = {}) {
    const W = 900, H = opts.height || 260, P = { t: 18, r: 12, b: 40, l: 42 };
    const max = Math.max(...data.map(d => d.value), 1);
    const svg = this._svg(W, H);
    const bw = (W - P.l - P.r) / data.length;
    const y = v => H - P.b - (v / max) * (H - P.t - P.b);
    for (let i = 0; i <= 4; i++) {
      const gy = P.t + (i * (H - P.t - P.b)) / 4;
      const line = document.createElementNS(SVGNS, 'line');
      line.setAttribute('x1', P.l); line.setAttribute('x2', W - P.r);
      line.setAttribute('y1', gy); line.setAttribute('y2', gy);
      line.setAttribute('class', 'gridline');
      svg.appendChild(line);
      this._t(svg, P.l - 8, gy + 4, ar(Math.round(max - (i * max) / 4)), { anchor: 'end', size: 10 });
    }
    data.forEach((d, i) => {
      const x = P.l + i * bw + bw * 0.16, w = bw * 0.68;
      const r = document.createElementNS(SVGNS, 'rect');
      r.setAttribute('x', x); r.setAttribute('y', y(d.value));
      r.setAttribute('width', w); r.setAttribute('height', Math.max(H - P.b - y(d.value), 1));
      r.setAttribute('rx', Math.min(6, w / 2));
      r.setAttribute('class', 'bar');
      const title = document.createElementNS(SVGNS, 'title');
      title.textContent = `${d.label}: ${num(d.value)}`;
      r.appendChild(title);
      svg.appendChild(r);
      if (data.length <= 40 || i % Math.ceil(data.length / 40) === 0)
        this._t(svg, x + w / 2, H - P.b + 18, d.label, { size: opts.labelSize || 12 });
    });
    container.innerHTML = '';
    container.appendChild(svg);
    return svg;
  },
  /* دائري (حلقي) */
  donut(container, data, opts = {}) {
    const W = 340, H = 300, cx = W / 2, cy = H / 2 + 6, R = 96, r = 60;
    const svg = this._svg(W, H);
    const total = data.reduce((a, d) => a + d.value, 0) || 1;
    const colors = opts.colors || ['#0e4a38', '#b08a2e', '#2a5d8f', '#8c3b46', '#14654c', '#d8b45a', '#4a5b53', '#7c8b83'];
    let a0 = -Math.PI / 2;
    data.forEach((d, i) => {
      const a1 = a0 + (d.value / total) * Math.PI * 2;
      const large = a1 - a0 > Math.PI ? 1 : 0;
      const p = (ang, rad) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)];
      const [x0, y0] = p(a0, R), [x1, y1] = p(a1, R), [x2, y2] = p(a1, r), [x3, y3] = p(a0, r);
      const path = document.createElementNS(SVGNS, 'path');
      path.setAttribute('d', `M${x0},${y0} A${R},${R} 0 ${large} 1 ${x1},${y1} L${x2},${y2} A${r},${r} 0 ${large} 0 ${x3},${y3} Z`);
      path.setAttribute('fill', colors[i % colors.length]);
      path.setAttribute('stroke', 'var(--panel)');
      path.setAttribute('stroke-width', '2');
      const t = document.createElementNS(SVGNS, 'title');
      t.textContent = `${d.label}: ${num(d.value)} (${(d.value / total * 100).toFixed(1)}%)`;
      path.appendChild(t);
      svg.appendChild(path);
      a0 = a1;
    });
    this._t(svg, cx, cy - 4, opts.centerLabel || num(total), { size: 19 });
    this._t(svg, cx, cy + 18, opts.centerSub || 'الإجمالي', { size: 11.5 });
    container.innerHTML = '';
    container.appendChild(svg);
    return svg;
  },
  /* شريط كثافة (لتوزيع الأجزاء/الصفحات) */
  heat(container, data, opts = {}) {
    const W = 900, H = opts.height || 96, P = { l: 8, r: 8, t: 8, b: 22 };
    const max = Math.max(...data.map(d => d.value), 1);
    const svg = this._svg(W, H);
    const bw = (W - P.l - P.r) / data.length;
    data.forEach((d, i) => {
      const h = (d.value / max) * (H - P.t - P.b);
      const r = document.createElementNS(SVGNS, 'rect');
      r.setAttribute('x', P.l + i * bw + 1);
      r.setAttribute('y', H - P.b - h);
      r.setAttribute('width', Math.max(bw - 2, 1));
      r.setAttribute('height', Math.max(h, 1.5));
      r.setAttribute('rx', 3);
      r.setAttribute('fill', `color-mix(in srgb, var(--green-2) ${35 + 65 * (d.value / max)}%, var(--gold))`);
      const t = document.createElementNS(SVGNS, 'title');
      t.textContent = `${d.label}: ${num(d.value)}`;
      r.appendChild(t);
      svg.appendChild(r);
      if (data.length <= 30 || i % Math.ceil(data.length / 30) === 0)
        this._t(svg, P.l + i * bw + bw / 2, H - 6, d.label, { size: 10 });
    });
    container.innerHTML = '';
    container.appendChild(svg);
    return svg;
  },
  /* قوائم حانات HTML (أوضح للأسماء العربية) */
  barlist(container, data, opts = {}) {
    const max = Math.max(...data.map(d => d.value), 1);
    // كل النصوص تمرّ عبر esc() — لا إدراج خام لأي بيانات قادمة من الخادم
    container.innerHTML = data.map(d => `
      <div class="barline">
        <div class="lbl" title="${esc(d.label)}">${esc(d.label)}</div>
        <div class="track"><div class="fill" style="width:${(d.value / max * 100).toFixed(2)}%"></div></div>
        <div class="val">${num(d.value)}${d.extra ? ' · ' + esc(d.extra) : ''}</div>
      </div>`).join('');
  },
};
