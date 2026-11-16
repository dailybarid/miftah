/* graph.js — شبكة الجذور والخريطة الذهنية (D3)
   مبادئ الرسم:
   • تخطيط مسبق متزامن (sim.tick) قبل أول رسم: لا اعتماد على مؤقّت المتصفح،
     فتظهر الشبكة مرتّبة من اللحظة الأولى بدل تكتّل العقد فوق بعضها.
   • تصادم يحسب عرض الوسم لا نصف الدائرة فقط، ولا تُوسم إلا العقد الأهم.
   • لا تُرسم كل الروابط (قد تكون آلافاً) بل أقواها فقط — والتخطيط يستخدمها كلها.
   • الخريطة الذهنية مواضعها محسوبة هندسياً (لا محاكاة) ومحجّمة لتدخل في اللوحة. */

const Graph = {
  palette: ['#0e4a38', '#b08a2e', '#2a5d8f', '#8c3b46', '#14654c', '#d8b45a', '#4a5b53', '#6b4f8a'],

  /* شبكة قوى: عقد = جذور */
  force(container, data, opts = {}) {
    container.innerHTML = '';
    const N = (data.nodes || []).length;
    if (!N) { container.innerHTML = '<div class="empty">لا توجد عقد لعرضها</div>'; return null; }
    const width = container.clientWidth || 900;
    const height = opts.height || Math.max(560, Math.min(880, 470 + N * 4));

    const svg = d3.select(container).append('svg')
      .attr('viewBox', [0, 0, width, height])
      .attr('width', '100%').attr('height', height);
    const root = svg.append('g');
    const inner = root.append('g');   // يُحجَّم ليملأ الإطار؛ والتكبير على المجموعة الأم
    svg.call(d3.zoom().scaleExtent([0.25, 5]).on('zoom', (ev) => root.attr('transform', ev.transform)));

    const nodes = data.nodes.map(d => Object.assign({}, d));
    // حماية: رابط يشير إلى عقدة غير موجودة يُسقط d3 بالكامل فلا يُرسم شيء
    const eid = l => (l && typeof l.source === 'object' ? l.source.id : l.source);
    const tid = l => (l && typeof l.target === 'object' ? l.target.id : l.target);
    const idset = new Set(nodes.map(n => n.id));
    const links = (data.links || []).filter(l => idset.has(eid(l)) && idset.has(tid(l)))
      .map(d => Object.assign({}, d));
    // حماية: بعض الرسوم لا تحمل أوزاناً (روابط تسلسل الكلمات مثلاً) — أي undefined
    // هنا كان يُنتج NaN في القوى فتتكدّس كل العقد فوق بعضها.
    const cnt = d => (Number.isFinite(+d.count) ? +d.count : 1);
    const wt = d => (Number.isFinite(+d.weight) ? +d.weight : 1);
    const maxC = d3.max(nodes, cnt) || 1;
    const maxW = d3.max(links, wt) || 1;

    // نصف القطر يتقلّص كلما زاد عدد العقد فلا تتراكم الدوائر الكبيرة
    const shrink = Math.min(1, Math.sqrt(70 / Math.max(70, N)));
    const radiusOf = d => (4.5 + 17 * Math.sqrt(cnt(d) / maxC)) * shrink;

    // الوسوم للعقد الأهم فقط (الأكثر وروداً) والباقي يظهر عند المرور
    const maxLabels = opts.maxLabels || Math.max(14, Math.min(34, Math.round(N / 2)));
    const labelled = new Set(nodes.slice()
      .sort((a, b) => cnt(b) - cnt(a))
      .slice(0, maxLabels).map(n => n.id));

    // لا نرسم آلاف الروابط: الأقوى فقط (التخطيط يستعمل الجميع)
    const maxLinks = opts.maxLinks || 420;
    const visible = links.slice().sort((a, b) => wt(b) - wt(a)).slice(0, maxLinks);

    const color = d => {
      const l = (d.label || '')[0] || '';
      return this.palette[(l.charCodeAt(0) || 0) % this.palette.length];
    };

    const link = inner.append('g').selectAll('line').data(visible).join('line')
      .attr('class', 'link')
      .attr('stroke-width', d => (0.4 + 2.4 * (wt(d) / maxW)) * shrink)
      .attr('stroke-opacity', d => 0.22 + 0.5 * (wt(d) / maxW));

    const node = inner.append('g').selectAll('g').data(nodes).join('g').attr('class', 'node');

    node.append('circle')
      .attr('r', radiusOf).attr('fill', color).attr('fill-opacity', .85);

    node.append('text')
      .text(d => d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => radiusOf(d) + 13)
      .attr('font-family', 'var(--quran-font)')
      .attr('font-size', d => (cnt(d) > maxC * 0.3 ? 14.5 : 11.5))
      .attr('opacity', d => (labelled.has(d.id) ? 1 : 0));

    node.on('mousemove', (ev, d) => {
      Tip.show(`<b>${esc(d.label)}</b><br>ورود الجذر: ${num(d.count)}<br>` +
               `في النطاق: ${num(d.ayat_in_scope)} آية (${pct(d.freq_in_scope, 1)})`, ev.clientX, ev.clientY);
      link.classed('hot', l => l.source.id === d.id || l.target.id === d.id);
      if (!labelled.has(d.id)) node.filter(x => x.id === d.id).select('text').attr('opacity', 1);
    }).on('mouseleave', (ev, d) => {
      Tip.hide();
      link.classed('hot', false);
      if (!labelled.has(d.id)) node.filter(x => x.id === d.id).select('text').attr('opacity', 0);
    }).on('click', (ev, d) => opts.onSelect && opts.onSelect(d));

    const render = () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    };

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id)
        .distance(d => (58 + 120 * (1 - wt(d) / maxW)) * Math.max(0.75, shrink))
        .strength(0.28))
      .force('charge', d3.forceManyBody()
        .strength(d => -(140 + 260 * Math.sqrt(cnt(d) / maxC)))
        .distanceMax(1.2 * Math.max(width, height)))
      .force('collide', d3.forceCollide()
        .radius(d => radiusOf(d) + (labelled.has(d.id) ? 12 : 7))
        .strength(1).iterations(2))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.06))
      .on('tick', render);

    // تخطيط مسبق متزامن: الشبكة مرتّبة قبل أن يراها المستخدم
    sim.stop();
    const ticks = Math.min(700, 240 + Math.round(N * 4));
    for (let i = 0; i < ticks; i++) sim.tick();
    render();

    // ملاءمة اللوحة: يُحسب امتداد العقد (مع هوامش الوسوم) ثم يُحجَّم الرسم ليملأ الإطار
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const d of nodes) {
      if (!Number.isFinite(d.x) || !Number.isFinite(d.y)) { d.x = width / 2; d.y = height / 2; }
      const r = radiusOf(d) + (labelled.has(d.id) ? 16 : 7);
      x0 = Math.min(x0, d.x - r); x1 = Math.max(x1, d.x + r);
      y0 = Math.min(y0, d.y - r); y1 = Math.max(y1, d.y + r);
    }
    if (!Number.isFinite(x0) || !Number.isFinite(x1) || x1 <= x0) { x0 = 0; x1 = width; }
    if (!Number.isFinite(y0) || !Number.isFinite(y1) || y1 <= y0) { y0 = 0; y1 = height; }
    const pad = 26;
    const fit = Math.max(0.25, Math.min(1.25,
      Math.min((width - 2 * pad) / Math.max(1, x1 - x0), (height - 2 * pad) / Math.max(1, y1 - y0))));
    inner.attr('transform',
      `translate(${width / 2},${height / 2}) scale(${fit}) translate(${-(x0 + x1) / 2},${-(y0 + y1) / 2})`);
    render();

    node.call(d3.drag()
      .on('start', (ev, d) => { if (!ev.active) sim.alpha(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
      .on('end', (ev, d) => { if (!ev.active) sim.alpha(0); d.fx = null; d.fy = null; }));

    return { sim, svg, node, link };
  },

  /* رسم الآية: طبقتان ثابتتان — الكلمات بترتيب المصحف (من اليمين) والجذور تحتها.
     التخطيط محسوب هندسياً لا بالمحاكاة: سلسلة الكلمات تمتدّ في رسم القوى إلى خط
     طويل يخرج من الإطار، أما الشِّبكة المرتّبة فتدخل دائماً ولا تتلاصق. */
  ayah(container, data, opts = {}) {
    container.innerHTML = '';
    const nodes = (data.nodes || []).map(n => Object.assign({}, n));
    const words = nodes.filter(n => n.type === 'word')
      .sort((a, b) => (a.n || 0) - (b.n || 0));
    const roots = nodes.filter(n => n.type !== 'word');
    if (!words.length) { container.innerHTML = '<div class="empty">لا توجد عقد لعرضها</div>'; return null; }

    const width = container.clientWidth || 900;
    const rowH = 146;
    // على الشاشات الضيقة تقلّ الهوامش ويُشتقّ التباعد من العرض المتاح،
    // فلا تخرج الكلمات عن الإطار ولا تتلاصق الجذور (كان step ثابتاً 58 فينفلت عند عرض < 360)
    const margin = Math.min(40, Math.max(18, width * 0.06));
    const perRow = Math.max(3, Math.min(16, Math.floor((width - 2 * margin) / 58)));
    const step = Math.min(58, (width - 2 * margin) / perRow);
    const wfs = step < 46 ? 12.5 : 15, rfs = step < 46 ? 10.5 : 12;
    const rows = Math.ceil(words.length / perRow);
    const height = opts.height || (rows * rowH + 70);
    // صفّ الكلمات من الأعلى، والجذور في نطاق أسفل كل صف
    const top = 58;
    const pos = new Map();
    words.forEach((w, i) => {
      const r = Math.floor(i / perRow), c = i % perRow;
      pos.set(w.id, { x: width - margin - c * step - step / 2, y: top + r * rowH });
    });
    // كل جذر تحت الكلمات التي يخدمها (وسطها)، مع تباعد جبري داخل النطاق
    const byRoot = new Map();
    for (const l of data.links || []) {
      if (l.kind !== 'root') continue;
      const w = pos.get(l.source), r = nodes.find(n => n.id === l.target);
      if (!w || !r) continue;
      const row = Math.floor((w.y - top) / rowH);
      const key = row;
      if (!byRoot.has(key)) byRoot.set(key, new Map());
      const m = byRoot.get(key);
      if (!m.has(r.id)) m.set(r.id, { node: r, xs: [] });
      m.get(r.id).xs.push(w.x);
    }
    for (const [row, m] of byRoot) {
      const list = [...m.values()].map(e => ({
        node: e.node, x: e.xs.reduce((a, b) => a + b, 0) / e.xs.length,
      })).sort((a, b) => a.x - b.x);
      let last = -Infinity;
      for (const e of list) {
        e.x = Math.max(e.x, last + Math.min(62, step), margin);
        last = e.x;
      }
      // إن تجاوزت الحدّ الأيسر، أعد التوزيع من اليسار
      const over = list.length ? list[list.length - 1].x - (width - margin) : 0;
      if (over > 0) for (const e of list) e.x = Math.max(margin, e.x - over);
      for (const e of list) pos.set(e.node.id, { x: e.x, y: top + row * rowH + 74 });
    }
    // جذور لم تُسند (بلا روابط) → صفّ أخير
    let orphan = 0;
    roots.forEach((r, i) => {
      if (pos.has(r.id)) return;
      pos.set(r.id, { x: width - margin - (orphan % perRow) * step - step / 2, y: top + rows * rowH + 30 });
      orphan++;
    });

    const svg = d3.select(container).append('svg')
      .attr('viewBox', [0, 0, width, height]).attr('width', '100%').attr('height', height);
    const g = svg.append('g');
    svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', ev => g.attr('transform', ev.transform)));

    const maxC = d3.max(roots, n => n.count || 1) || 1;
    const rOf = n => (n.type === 'word' ? 12 : 6.5 + 7 * Math.sqrt(((n.count || 1) / maxC)));

    const links = (data.links || []).filter(l => pos.has(l.source) && pos.has(l.target));
    const seq = links.filter(l => l.kind === 'sequence');
    const rt = links.filter(l => l.kind !== 'sequence');
    g.append('g').selectAll('line').data(seq).join('line')
      .attr('class', 'link seq')
      .attr('x1', l => pos.get(l.source).x).attr('y1', l => pos.get(l.source).y)
      .attr('x2', l => pos.get(l.target).x).attr('y2', l => pos.get(l.target).y);
    g.append('g').selectAll('line').data(rt).join('line')
      .attr('class', 'link')
      .attr('x1', l => pos.get(l.source).x).attr('y1', l => pos.get(l.source).y)
      .attr('x2', l => pos.get(l.target).x).attr('y2', l => pos.get(l.target).y)
      .attr('stroke-dasharray', '3 3');

    const node = g.append('g').selectAll('g')
      .data(nodes.filter(n => pos.has(n.id))).join('g').attr('class', 'node')
      .attr('transform', d => { const p = pos.get(d.id); return `translate(${p.x},${p.y})`; });
    node.append('circle').attr('r', rOf).attr('fill',
      d => (d.type === 'word' ? '#0e4a38' : '#b08a2e')).attr('fill-opacity', .88);
    // وسم الكلمة فوقها (الصف أعلى)، ووسم الجذر تحته
    node.append('text')
      .text(d => d.label)
      .attr('font-family', 'var(--quran-font)')
      .attr('font-size', d => (d.type === 'word' ? wfs : rfs))
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.type === 'word' ? -rOf(d) - 7 : rOf(d) + 13));

    node.on('mousemove', (ev, d) => Tip.show(
      `<b>${esc(d.label)}</b><br>${d.type === 'word' ? 'كلمة' : 'جذر'}` +
      (d.pos ? `<br>${esc(d.pos)}` : '') + (d.count ? `<br>ورود الجذر: ${num(d.count)}` : ''),
      ev.clientX, ev.clientY))
      .on('mouseleave', () => Tip.hide())
      .on('click', (ev, d) => { if (d.type === 'root') location.hash = '#/root/' + d.id; });

    return { svg, node, fit: 1 };
  },

  /* خريطة ذهنية شعاعية حول جذر — مواضع محسوبة هندسياً، ثابتة، ومحجّمة لتدخل في اللوحة */
  mindmap(container, data, opts = {}) {
    container.innerHTML = '';
    const width = container.clientWidth || 900;
    const height = opts.height || 620;
    const nodes = (data.nodes || []).map(n => Object.assign({}, n));
    const rootNode = nodes.find(n => n.level === 0) || nodes[0];
    if (!rootNode) { container.innerHTML = '<div class="empty">لا توجد عقد لعرضها</div>'; return null; }

    const byId = new Map(nodes.map(n => [n.id, n]));
    const links = (data.links || []).map(l => ({
      source: l.source, target: l.target, weight: l.weight,
      s: byId.get(l.source), t: byId.get(l.target),
    })).filter(l => l.s && l.t);

    const maxC = d3.max(nodes, n => n.count) || 1;
    // حماية موازية لحماية force(): لا وزن ⇒ لا NaN في سمك الروابط
    const wt = l => (Number.isFinite(+l.weight) ? +l.weight : 1);
    const radiusOf = n => (n.level === 0 ? 15 + 17 * Math.sqrt((n.count || 1) / maxC)
                                         : 5 + 13 * Math.sqrt((n.count || 1) / maxC));
    // وزن الرابط من البذرة يحدّد ترتيب الجيران حولها
    const wOf = new Map();
    for (const l of links) if (l.s.id === rootNode.id) wOf.set(l.t.id, l.weight);
    const leaves = nodes.filter(n => n.level > 0)
      .sort((a, b) => (wOf.get(b.id) || b.count || 0) - (wOf.get(a.id) || a.count || 0));

    // توزيع الجيران على حلقات: سعة الحلقة تتناسب مع محيطها كي لا تتلاصق العقد
    const pos = new Map([[rootNode.id, { x: 0, y: 0 }]]);
    let i = 0, ring = 0, maxR = 0;
    while (i < leaves.length && ring < 24) {
      const r = 155 + ring * 132;
      const cap = Math.max(6, Math.floor((2 * Math.PI * r) / 82));
      const n = Math.min(cap, leaves.length - i);
      for (let k = 0; k < n; k++) {
        const ang = (k / n) * 2 * Math.PI + (ring % 2 ? Math.PI / n : 0);
        pos.set(leaves[i + k].id, { x: Math.cos(ang) * r, y: Math.sin(ang) * r });
        maxR = Math.max(maxR, r);
      }
      i += n; ring++;
    }
    // تحجيم ليحتوي اللوحة (مع هامش للوسوم الجانبية)
    const fit = Math.min(1, ((Math.min(width, height) / 2) - 52) / Math.max(1, maxR));

    const svg = d3.select(container).append('svg')
      .attr('viewBox', [0, 0, width, height]).attr('width', '100%').attr('height', height);
    const g = svg.append('g').attr('transform', `translate(${width / 2},${height / 2}) scale(${fit})`);
    svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', ev => g.attr('transform',
      `translate(${width / 2},${height / 2}) scale(${fit * ev.transform.k})`)));

    const maxW = d3.max(links, wt) || 1;
    const color = n => {
      const l = (n.label || '')[0] || '';
      return this.palette[(l.charCodeAt(0) || 0) % this.palette.length];
    };

    // روابط من الجذر إلى الطبقة الأولى + روابط الطبقة الثانية
    g.append('g').selectAll('line').data(links).join('line')
      .attr('class', 'link')
      .attr('x1', l => pos.get(l.source).x).attr('y1', l => pos.get(l.source).y)
      .attr('x2', l => pos.get(l.target).x).attr('y2', l => pos.get(l.target).y)
      .attr('stroke-width', l => 0.5 + 2.6 * (wt(l) / maxW) * (l.s.level === 0 ? 1 : 0.6))
      .attr('stroke-opacity', l => l.s.level === 0 ? 0.75 : 0.35);

    // الوسوم: الجذر دائماً، والجيران الأبرز فقط (الباقي عند المرور)
    const maxLabels = opts.maxLabels || 26;
    const median = (() => {
      const c = leaves.map(n => n.count || 0).sort((a, b) => a - b);
      return c.length ? c[Math.floor(c.length / 2)] : 0;
    })();
    const labelled = new Set(leaves.slice(0, maxLabels)
      .filter(n => (n.count || 0) >= median).map(n => n.id));
    labelled.add(rootNode.id);

    const node = g.append('g').selectAll('g').data(nodes).join('g').attr('class', 'node')
      .attr('transform', d => { const p = pos.get(d.id); return `translate(${p.x},${p.y})`; });

    node.append('circle').attr('r', radiusOf)
      .attr('fill', color).attr('fill-opacity', d => (d.level === 0 ? 1 : .82));

    // وسم الجيران يوضع جانب العقدة (خارج الدائرة) لتفادي التصادم
    node.append('text')
      .text(d => d.label)
      .attr('font-family', 'var(--quran-font)')
      .attr('font-size', d => (d.level === 0 ? 19 : 12.5))
      .attr('text-anchor', d => (d.level === 0 ? 'middle' : (pos.get(d.id).x >= 0 ? 'start' : 'end')))
      .attr('dx', d => (d.level === 0 ? 0 : (pos.get(d.id).x >= 0 ? radiusOf(d) + 6 : -(radiusOf(d) + 6))))
      .attr('dy', d => (d.level === 0 ? radiusOf(d) + 17 : 4.5))
      .attr('opacity', d => (labelled.has(d.id) ? 1 : 0));

    node.on('mousemove', (ev, d) => {
      Tip.show(`<b>${esc(d.label)}</b><br>ورود الجذر: ${num(d.count)}` +
               (d.level ? `<br>الطبقة: ${ar(d.level)}` : '<br>البذرة'), ev.clientX, ev.clientY);
      if (!labelled.has(d.id)) node.filter(x => x.id === d.id).select('text').attr('opacity', 1);
    }).on('mouseleave', (ev, d) => {
      Tip.hide();
      if (!labelled.has(d.id)) node.filter(x => x.id === d.id).select('text').attr('opacity', 0);
    }).on('click', (ev, d) => opts.onSelect && opts.onSelect(d.label));

    return { svg, node, fit };
  },
};
