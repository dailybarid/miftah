/* graph.js — شبكة الجذور والخريطة الذهنية (D3) */

const Graph = {
  palette: ['#0e4a38', '#b08a2e', '#2a5d8f', '#8c3b46', '#14654c', '#d8b45a', '#4a5b53', '#6b4f8a'],

  /* شبكة قوى: عقد = جذور */
  force(container, data, opts = {}) {
    container.innerHTML = '';
    const width = container.clientWidth || 900;
    const height = opts.height || 620;
    const svg = d3.select(container).append('svg')
      .attr('viewBox', [0, 0, width, height])
      .attr('width', '100%').attr('height', height);

    const root = svg.append('g');
    svg.call(d3.zoom().scaleExtent([0.25, 5]).on('zoom', (ev) => root.attr('transform', ev.transform)));

    const nodes = data.nodes.map(d => Object.assign({}, d));
    const links = data.links.map(d => Object.assign({}, d));
    const maxC = d3.max(nodes, d => d.count) || 1;
    const maxW = d3.max(links, d => d.weight) || 1;

    const link = root.append('g').selectAll('line').data(links).join('line')
      .attr('class', 'link')
      .attr('stroke-width', d => 0.4 + 3.2 * (d.weight / maxW));

    const node = root.append('g').selectAll('g').data(nodes).join('g')
      .attr('class', 'node');

    const color = d => {
      const l = (d.label || '')[0] || '';
      const idx = (l.charCodeAt(0) || 0) % this.palette.length;
      return this.palette[idx];
    };

    node.append('circle')
      .attr('r', d => 4 + 20 * Math.sqrt((d.count || 1) / maxC))
      .attr('fill', color)
      .attr('fill-opacity', .85);

    node.append('text')
      .text(d => d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => 4 + 20 * Math.sqrt((d.count || 1) / maxC) + 13)
      .attr('font-family', 'var(--quran-font)')
      .attr('font-size', d => (d.count || 0) > maxC * 0.3 ? 15 : 12);

    node.on('mousemove', (ev, d) => {
      Tip.show(`<b>${esc(d.label)}</b><br>ورود الجذر: ${num(d.count)}<br>` +
               `في النطاق: ${num(d.ayat_in_scope)} آية (${pct(d.freq_in_scope, 1)})`, ev.clientX, ev.clientY);
      link.classed('hot', l => l.source.id === d.id || l.target.id === d.id);
    }).on('mouseleave', () => { Tip.hide(); link.classed('hot', false); })
      .on('click', (ev, d) => opts.onSelect && opts.onSelect(d));

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(d => 60 + 120 * (1 - d.weight / maxW)).strength(0.35))
      .force('charge', d3.forceManyBody().strength(d => -120 - 260 * Math.sqrt((d.count || 1) / maxC)))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(d => 8 + 22 * Math.sqrt((d.count || 1) / maxC)))
      .on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });

    node.call(d3.drag()
      .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
      .on('end', (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    return { sim, svg, node, link };
  },

  /* خريطة ذهنية شعاعية حول جذر */
  mindmap(container, data, opts = {}) {
    container.innerHTML = '';
    const width = container.clientWidth || 900;
    const height = opts.height || 660;
    const svg = d3.select(container).append('svg')
      .attr('viewBox', [0, 0, width, height]).attr('width', '100%').attr('height', height);
    const g = svg.append('g').attr('transform', `translate(${width / 2},${height / 2})`);
    svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', ev => g.attr('transform',
      `translate(${width / 2},${height / 2}) scale(${ev.transform.k})`)));

    const byId = new Map(data.nodes.map(n => [n.id, n]));
    const color = id => {
      const l = (byId.get(id)?.label || '')[0] || '';
      return this.palette[(l.charCodeAt(0) || 0) % this.palette.length];
    };
    const links = data.links.map(l => ({
      source: l.source, target: l.target, weight: l.weight,
      s: byId.get(l.source), t: byId.get(l.target),
    })).filter(l => l.s && l.t);

    const maxW = d3.max(links, l => l.weight) || 1;
    const maxC = d3.max(data.nodes, n => n.count) || 1;
    const radiusOf = n => 5 + 19 * Math.sqrt((n.count || 1) / maxC);

    const link = g.append('g').selectAll('line').data(links).join('line')
      .attr('class', 'link').attr('stroke-width', l => 0.5 + 3 * (l.weight / maxW));

    const node = g.append('g').selectAll('g').data(data.nodes).join('g').attr('class', 'node')
      .attr('transform', d => d.level === 0 ? 'translate(0,0)' : '');

    node.filter(d => d.level > 0).each(function (d) {
      const ang = 2 * Math.PI * (d.__i || 0);
      d.x = Math.cos(ang) * 220; d.y = Math.sin(ang) * 220; d.fx = d.x; d.fy = d.y;
    });

    node.append('circle').attr('r', radiusOf)
      .attr('fill', d => color(d.id)).attr('fill-opacity', d => d.level === 0 ? 1 : .8);
    node.append('text').text(d => d.label).attr('text-anchor', 'middle')
      .attr('dy', d => radiusOf(d) + 14).attr('font-family', 'var(--quran-font)')
      .attr('font-size', d => d.level === 0 ? 20 : 13);

    node.on('mousemove', (ev, d) => Tip.show(`<b>${esc(d.label)}</b><br>ورود الجذر: ${num(d.count)}` +
        (d.level ? `<br>الطبقة: ${ar(d.level)}` : '<br>البذرة'), ev.clientX, ev.clientY))
      .on('mouseleave', () => Tip.hide())
      .on('click', (ev, d) => opts.onSelect && opts.onSelect(d.label));

    // توزيع الجيران على محيط دائرة: يُرتَّب الهدف حسب ثقل الرابط
    const leaves = data.nodes.filter(n => n.level > 0);
    const groupOf = new Map();
    for (const l of links) {
      if (l.s && l.s.level === 0) groupOf.set(l.target, l.weight);
    }
    const ordered = leaves.map(n => ({ n, w: groupOf.get(n.id) || n.count }))
      .sort((a, b) => b.w - a.w);
    const total = ordered.length || 1;
    const maxB = opts.branch || 8;
    ordered.forEach((o, i) => {
      const ring = Math.floor(i / maxB);
      const within = i % maxB;
      const perRing = Math.min(maxB, total - ring * maxB) || 1;
      const ang = (within / perRing) * 2 * Math.PI + (ring % 2) * Math.PI / perRing;
      const rad = 170 + ring * 150;
      o.n.radius = rad; o.n.angle = ang;
    });

    const sim = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(l => l.t && l.t.radius ? l.t.radius : 180).strength(.25))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('collide', d3.forceCollide().radius(d => radiusOf(d) + 9))
      .on('tick', () => {
        for (const n of data.nodes) if (n.radius && n.fx == null) {
          n.x = Math.cos(n.angle) * n.radius; n.y = Math.sin(n.angle) * n.radius;
        }
        link.attr('x1', l => l.s.x).attr('y1', l => l.s.y).attr('x2', l => l.t.x).attr('y2', l => l.t.y);
        node.attr('transform', d => `translate(${d.x || 0},${d.y || 0})`);
      });
    return { sim, svg };
  },
};
