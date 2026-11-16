/* views.js — كل شاشات التطبيق */

const RECITERS = [
  ['Alafasy_128kbps', 'مشاري العفاسي'],
  ['Husary_128kbps', 'محمود خليل الحصري'],
  ['Minshawy_Murattal_128kbps', 'محمد المنشاوي (مرتل)'],
  ['Abdul_Basit_Murattal_192kbps', 'عبد الباسط (مرتل)'],
  ['Ghamadi_40kbps', 'سعد الغامدي'],
];

const V = {
  _meta: null,
  async meta() {
    if (!this._meta) this._meta = await API.meta();
    return this._meta;
  },

  /* ------------------------------ عناصر مشتركة ------------------------------ */
  crumbs(items) {
    return `<div class="breadcrumbs">${items.map((it, i) =>
      (it.href ? `<a href="${it.href}">${esc(it.label)}</a>` : `<span>${esc(it.label)}</span>`) +
      (i < items.length - 1 ? '<span>›</span>' : '')).join('')}</div>`;
  },

  wordSpans(match) {
    const hits = new Set((match.matched_words || []).map(w => w.number_in_ayah));
    return (match.words || []).map(w =>
      `<span class="w${w.m ? ' hit' : ''}" data-word="w" data-ref="${match.sura}:${match.ayah}" data-n="${w.n}"
             title="الكلمة ${ar(w.n)} · ${ar(w.l)} حروف — اضغط للتفصيل">${esc(w.t)}</span>`
    ).join(' ') + `<span class="medallion">${ar(match.ayah)}</span>`;
  },

  verseCard(match, opts = {}) {
    const p = match.positions || {};
    const chips = [
      `الجزء ${ar(p.juz)}`, `الحزب ${ar(p.hizb)}`, `الربع ${ar(p.rub)}`,
      `الصفحة ${ar(p.page)}`, `المنزل ${ar(p.manzil)}`, `الرُّكوع ${ar(p.ruku)}`,
      `الآية ${ar(p.ayah_in_sura)} من ${ar(match.sura)}:${ar(match.ayah)}`.replace(/.*/, `الترتيب في المصحف ${ar(p.ayah_in_quran)}`),
      p.sajda ? `موضع سجدة (${p.sajda_type === 'obligatory' ? 'مؤكدة' : 'مستحبة'})` : null,
    ].filter(Boolean);
    const mw = (match.matched_words || []).map(w => `
      <tr>
        <td class="num">${ar(w.number_in_ayah)}</td>
        <td style="font-family:var(--quran-font);font-size:21px">${esc(w.text)}</td>
        <td>${esc(w.pos_ar || '—')}</td>
        <td>${w.root ? esc(w.root) : '—'}</td>
        <td class="num">${ar(w.letters)}</td>
        <td class="num">${ar(w.letter_start_in_ayah)}</td>
        <td class="num">${num(w.letter_start_in_quran)}</td>
      </tr>`).join('');
    return `
    <article class="verse" data-ayah="${match.sura}:${match.ayah}">
      <div class="head">
        <span class="ref" data-goto="${match.sura}/${match.ayah}">سورة ${esc(match.sura_name)} · الآية ${ar(match.ayah)}</span>
        <div class="meta">${chips.map(c => `<span class="chip stat">${c}</span>`).join('')}</div>
      </div>
      <div class="text">${this.wordSpans(match)}</div>
      <div class="meta">
        <span class="chip stat">كلمات ${ar(p.words_in_ayah)}</span>
        <span class="chip stat">حروف ${ar(p.letters_in_ayah)}</span>
        <span class="chip stat">محارف ${num(p.chars_in_ayah)}</span>
        <span class="chip stat">حركات ${num(p.diacritics_in_ayah)}</span>
        <span class="chip stat">حروف مختلفة ${ar(p.distinct_letters_in_ayah)}</span>
        <span class="chip stat">قيمة الجُمّل ${num(p.abjad_value)}</span>
        <span class="chip stat">نصيب الآية من حروف القرآن ${pct(p.ayah_text_share_letters, 4)}</span>
      </div>
      ${mw ? `<details class="more"><summary>مواضع الكلمات المطابقة (${ar((match.matched_words || []).length)})</summary>
        <div class="scroll-x"><table class="tbl">
          <thead><tr><th>#</th><th>الكلمة</th><th>النوع</th><th>الجذر</th><th>الحروف</th><th>الحرف الأول في الآية</th><th>الحرف في المصحف</th></tr></thead>
          <tbody>${mw}</tbody></table></div></details>` : ''}
      <div class="actions">
        <button data-copy="${esc(match.text_uthmani)}" data-copy-ref="${match.sura}:${match.ayah}">نسخ الآية</button>
        <button data-goto="${match.sura}/${match.ayah}">صفحة الآية والتحليل</button>
        <button data-graph-ayah="${match.sura}/${match.ayah}">شبكة الآية</button>
        <button data-audio="${match.sura}:${match.ayah}">تلاوة</button>
        <button data-share>رابط مباشر</button>
      </div>
    </article>`;
  },

  /* ------------------------------ الرئيسية ------------------------------ */
  async home(main) {
    const m = await this.meta();
    const t = m.totals;
    const st = await API.stats();
    let topics = [];
    try { topics = (await API.topics()).topics || []; } catch (e) { topics = []; }
    main.innerHTML = `
      <h1 class="page">مِفتاح — البحث في القرآن الكريم بكل تفاصيله</h1>
      <p class="lede">بحث دقيق يحترم الرسم العثماني والتشكيل، مع مواضع كل كلمة وحرف: السورة، الآية،
      رقم الكلمة، رقم الحرف في الآية وفي المصحف، الجزء والحزب والربع والصفحة، وإحصاءات الحروف والحركات،
      وربط كل كلمة بجذرها الصرفي، وشبكات علاقات بين الجذور وخريطة ذهنية.</p>

      <div class="grid cols-4">
        ${this.tile('الآيات', num(t.ayahs))}
        ${this.tile('الكلمات', num(t.words))}
        ${this.tile('الحروف', num(t.letters))}
        ${this.tile('الحركات', num(t.diacritics))}
        ${this.tile('الجذور', num(t.roots))}
        ${this.tile('الموارد الصرفية', num(t.lemmas))}
        ${this.tile('صيغ الكلمات المختلفة', num(t.distinct_words))}
        ${this.tile('حروف مختلفة', num(t.distinct_letters))}
      </div>

      <div class="card">
        <h3>ابدأ البحث</h3>
        <div class="chips">
          ${['الرحمن', 'الصلاة', 'الكتاب', 'نور', 'جذر:رحم', '2:255', 'كهيعص', 'محمدرسول']
            .map(q => `<button class="chip" data-quick="${esc(q)}">${esc(q)}</button>`).join('')}
        </div>
      </div>

      ${this._topicsTeaser(topics)}

      <div class="grid cols-2">
        <div class="card"><h3>توزيع الآيات على الأجزاء الثلاثين</h3><div id="juzchart" class="chart"></div></div>
        <div class="card"><h3>أكثر الحروف وروداً في المصحف</h3><div id="letterchart" class="chart"></div>
          <div class="note" style="margin-top:10px">الحروف بعد توحيد الألف والهمزات، والحركات والعلامات مستثناة.</div></div>
      </div>

      <div class="grid cols-2">
        <div class="card"><h3>أطول الآيات</h3>
          <ul class="list">${st.longest_ayat.map(a => `<li data-goto="${a.sura}/${a.number}">
            <span class="lead">${ar(a.sura)}:${ar(a.number)}</span>
            <span class="mid">${esc((st.suras.find(s => s.number === a.sura) || {}).name_ar || '')}</span>
            <span class="end">${ar(a.word_count)} كلمة · ${ar(a.letter_count)} حرفاً</span></li>`).join('')}</ul></div>
        <div class="card"><h3>أقصر الآيات</h3>
          <ul class="list">${st.shortest_ayat.map(a => `<li data-goto="${a.sura}/${a.number}">
            <span class="lead">${ar(a.sura)}:${ar(a.number)}</span>
            <span class="mid">${esc((st.suras.find(s => s.number === a.sura) || {}).name_ar || '')}</span>
            <span class="end">${ar(a.word_count)} كلمة · ${ar(a.letter_count)} حرفاً</span></li>`).join('')}</ul></div>
      </div>

      <div class="grid cols-2">
        <div class="card"><h3>أكثر الجذور وروداً</h3><div id="rootbars" class="bars"></div></div>
        <div class="card"><h3>أكثر الكلمات وروداً (كل كلمة وسم)</h3><div id="wordbars" class="bars"></div></div>
      </div>

      <div class="card">
        <h3>الأنماط النحوية في المصحف</h3>
        <div class="grid cols-2">
          <div id="posdonut"></div>
          <div class="scroll-x"><table class="tbl"><thead><tr><th>النمط</th><th>عدد الكلمات</th><th>عدد الصيغ</th><th>عدد السور</th></tr></thead>
            <tbody>${st.pos.slice(0, 14).map(p => `<tr><td>${esc(p.pos_ar)}</td><td class="num">${num(p.count)}</td>
            <td class="num">${ar(p.word_count)}</td><td class="num">${ar(p.sura_count)}</td></tr>`).join('')}</tbody></table></div>
        </div>
      </div>`;

    Chart.bars(document.getElementById('juzchart'),
      st.by_juz.map(j => ({ label: ar(j.juz), value: j.ayat })), { height: 240 });
    const letters = (st.letters || []).filter(l => l.kind === 'norm').slice(0, 20);
    Chart.bars(document.getElementById('letterchart'),
      letters.map(l => ({ label: l.letter, value: l.count })), { height: 240, labelSize: 15 });
    Chart.barlist(document.getElementById('rootbars'),
      st.top_roots.slice(0, 12).map(r => ({ label: r.arabic, value: r.count, extra: `${ar(r.form_count)} صيغة` })));
    Chart.barlist(document.getElementById('wordbars'),
      st.top_words.slice(0, 12).map(w => ({ label: w.text_norm, value: w.count, extra: `${ar(w.sura_count)} سورة` })));
    Chart.donut(document.getElementById('posdonut'),
      st.pos.filter(p => ['N', 'V', 'P', 'PRON', 'DET', 'CONJ', 'ADJ', 'PN'].includes(p.pos))
        .map(p => ({ label: p.pos_ar, value: p.count })),
      { centerLabel: num(t.words), centerSub: 'كلمة' });
  },

  tile(k, v, s = '') {
    return `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;
  },

  /* بطاقة مختصرة للمحاور الموضوعية في الصفحة الرئيسية (تظهر فقط إذا بُنيت المحاور) */
  _topicsTeaser(topics) {
    if (!topics || !topics.length) return '';
    return `
      <div class="card">
        <h3>المحاور الموضوعية <span style="font-size:13px;color:var(--ink-faint)">(${ar(topics.length)} محوراً — اضغط للتفصيل)</span></h3>
        <div class="chips">
          ${topics.slice(0, 12).map(t => `<button class="chip" data-nav="topics">
            <span style="font-family:var(--quran-font);font-size:16px">${esc(t.label)}</span>
            <span style="color:var(--ink-faint)"> ${ar(t.size)}</span></button>`).join('')}
        </div>
      </div>`;
  },

  /* ------------------------------ نتائج البحث ------------------------------ */
  async results(main, params) {
    const q = params.get('q') || '';
    if (!q) return this.searchForm(main, params);
    const p = {
      q, mode: params.get('mode') || 'word_contains',
      tashkeel: params.get('tashkeel') === '1',
      limit: +(params.get('limit') || 25), offset: +(params.get('offset') || 0),
      ignore_tashkeel: params.get('it') !== '0', unify_alef: params.get('ua') !== '0',
      unify_ya: params.get('uy') !== '0', unify_ta: params.get('ut') !== '0',
      ignore_hamza: params.get('ih') === '1',
      sura: params.get('sura') || '', juz: params.get('juz') || '',
      page_min: params.get('pmin') || '', page_max: params.get('pmax') || '',
      revelation: params.get('rev') || '', sajda: params.get('sajda') === '1' ? true : '',
      words_min: params.get('wmin') || '', words_max: params.get('wmax') || '',
      letters_min: params.get('lmin') || '', letters_max: params.get('lmax') || '',
      proximity: +(params.get('prox') || 0),
    };
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    let r;
    try { r = await API.search(p); }
    catch (e) { main.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }

    if (r.kind === 'ayah_reference') { return this.ayah(main, +p.q.split(/[:/.]/)[0], +p.q.split(/[:/.]/)[1]); }
    if (r.kind === 'root' && r.root) { return this.rootById(main, r.root.root.id); }
    if (r.kind === 'root_list') { return this.rootList(main, r.roots); }

    const s = r.stats || {};
    const statsBlock = s.occurrences ? `
      <div class="card">
        <h3>إحصاءات المواضع</h3>
        <div class="grid cols-4">
          ${this.tile('عدد المواضع', num(s.occurrences))}
          ${this.tile('عدد الآيات', num(s.ayat), `من ${num(6236)} = ${pct(s.ayat_ratio, 2)}`)}
          ${this.tile('عدد السور', ar(s.suras))}
          ${this.tile('أول موضع', s.first_occurrence.ref, `الكلمة ${num(s.first_occurrence.word_index_in_quran)} في المصحف`)}
          ${this.tile('آخر موضع', s.last_occurrence.ref, `الكلمة ${num(s.last_occurrence.word_index_in_quran)} في المصحف`)}
          ${this.tile('امتداد التوزيع', num(s.span_words) + ' كلمة', 'بين أول وآخر موضع')}
        </div>
        <div class="grid cols-2" style="margin-top:14px">
          <div><h3>التوزيع على السور (الأعلى)</h3><div id="surachart" class="chart"></div></div>
          <div><h3>التوزيع على الأجزاء</h3><div id="juzchart2" class="chart"></div></div>
        </div>
        <div class="grid cols-2" style="margin-top:14px">
          <div><h3>الموضع داخل الآية</h3><div id="placebars" class="bars"></div></div>
          <div><h3>الأنماط النحوية للمواضع</h3><div id="posbars" class="bars"></div></div>
        </div>
        <div class="grid cols-2" style="margin-top:14px">
          <div><h3>مكية/مدنية</h3><div id="revdonut"></div></div>
          <div><h3>الصفحات (أول 24 صفحة فيها ورود)</h3><div id="pageheat" class="chart"></div></div>
        </div>
      </div>` : '';

    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'نتائج البحث' }])}
      <h1 class="page">نتائج البحث: «${esc(r.query)}»</h1>
      <p class="lede">
        ${num(r.count)} نتيجة · زمن التنفيذ ${ar(r.elapsed_ms)} م.ث ·
        الصيغة المطبَّعة للبحث: <code>${esc(r.normalized || '')}</code> ·
        النمط: ${esc({ word_contains: 'ضمن الكلمة', word_exact: 'كلمة تامة', word_prefix: 'بداية الكلمة', word_suffix: 'نهاية الكلمة', anywhere: 'حروف في أي موضع', letters_across: 'حروف متصلة عبر الكلمات', phrase: 'عبارة' }[r.mode] || r.mode)}
        ${p.tashkeel ? ' · <strong>احترام التشكيل مفعّل</strong>' : ''}
      </p>
      ${this.optionsPanel(p, r.count)}
      ${statsBlock}
      <div id="list">${r.matches.map(m => this.verseCard(m)).join('')}</div>
      ${this.pager(p, r.count, p.limit, p.offset)}`;

    if (s.by_sura) Chart.bars(document.getElementById('surachart'),
      s.by_sura.slice(0, 14).map(x => ({ label: x.name_ar, value: x.c, html: true })), { height: 260, labelSize: 11 });
    if (s.by_juz) Chart.bars(document.getElementById('juzchart2'),
      s.by_juz.map(x => ({ label: ar(x.juz), value: x.c })), { height: 260 });
    if (s.by_place_in_ayah) Chart.barlist(document.getElementById('placebars'),
      s.by_place_in_ayah.map(x => ({ label: x.place, value: x.c })));
    if (s.by_pos) Chart.barlist(document.getElementById('posbars'),
      s.by_pos.map(x => ({ label: x.pos_ar || x.pos, value: x.c })));
    if (s.by_revelation) Chart.donut(document.getElementById('revdonut'),
      s.by_revelation.map(x => ({ label: x.revelation, value: x.c })), { centerLabel: num(r.count), centerSub: 'موضعاً' });
    if (s.by_page) Chart.heat(document.getElementById('pageheat'),
      s.by_page.slice(0, 40).map(x => ({ label: ar(x.page), value: x.c })), { height: 130 });
  },

  optionsPanel(p, count) {
    return `
    <div class="options">
      <div class="row">
        <div class="field"><label>نمط المطابقة</label>
          <select id="opt-mode">
            ${[['word_contains', 'ضمن الكلمة'], ['word_exact', 'كلمة تامة'], ['word_prefix', 'بداية الكلمة'],
               ['word_suffix', 'نهاية الكلمة'], ['anywhere', 'حروف متتالية في أي موضع'],
               ['letters_across', 'حروف متصلة عبر الكلمات'], ['phrase', 'عبارة (كلمات متتابعة)']]
              .map(([v, t]) => `<option value="${v}" ${p.mode === v ? 'selected' : ''}>${t}</option>`).join('')}
          </select></div>
        <label class="switch"><input type="checkbox" id="opt-tashkeel" ${p.tashkeel ? 'checked' : ''}> احترام التشكيل المكتوب</label>
        <label class="switch"><input type="checkbox" id="opt-it" ${p.ignore_tashkeel ? 'checked' : ''}> تجاهل تشكيل النص</label>
        <label class="switch"><input type="checkbox" id="opt-ua" ${p.unify_alef ? 'checked' : ''}> توحيد الألف (آ أ إ ٱ ← ا)</label>
        <label class="switch"><input type="checkbox" id="opt-uy" ${p.unify_ya ? 'checked' : ''}> توحيد الياء (ى ← ي)</label>
        <label class="switch"><input type="checkbox" id="opt-ut" ${p.unify_ta ? 'checked' : ''}> توحيد التاء المربوطة (ة ← ه)</label>
        <label class="switch"><input type="checkbox" id="opt-ih" ${p.ignore_hamza ? 'checked' : ''}> تجاهل الهمزات (ؤ ئ ء)</label>
      </div>
      <div class="row">
        <div class="field"><label>سورة (أرقام مفصولة بفاصلة)</label><input id="f-sura" value="${esc(p.sura || '')}" placeholder="2, 3, 112"></div>
        <div class="field"><label>الجزء</label><input id="f-juz" value="${esc(p.juz || '')}" placeholder="30"></div>
        <div class="field"><label>من صفحة</label><input id="f-pmin" type="number" value="${esc(p.page_min || '')}" placeholder="1"></div>
        <div class="field"><label>إلى صفحة</label><input id="f-pmax" type="number" value="${esc(p.page_max || '')}" placeholder="604"></div>
        <div class="field"><label>مكية/مدنية</label><select id="f-rev">
          <option value="">الكل</option>
          <option value="مكية" ${p.revelation === 'مكية' ? 'selected' : ''}>مكية</option>
          <option value="مدنية" ${p.revelation === 'مدنية' ? 'selected' : ''}>مدنية</option>
        </select></div>
        <div class="field"><label>أقل عدد كلمات في الآية</label><input id="f-wmin" type="number" value="${esc(p.words_min || '')}"></div>
        <div class="field"><label>أكثر عدد كلمات</label><input id="f-wmax" type="number" value="${esc(p.words_max || '')}"></div>
        <label class="switch"><input type="checkbox" id="f-sajda" ${p.sajda ? 'checked' : ''}> آيات السجد فقط</label>
      </div>
      <div class="row">
        <button class="chip" id="apply" style="background:var(--green);color:#fff;border-color:var(--green)">تطبيق الخيارات</button>
        <button class="chip" id="reset">تصفير</button>
        <span class="chip stat">النتائج: ${num(count)}</span>
        <details style="flex:1">
          <summary style="cursor:pointer;color:var(--ink-faint);font-size:13.5px">مساعدة بصيغ البحث</summary>
          <div style="font-size:13.5px;color:var(--ink-soft);margin-top:6px">
            <div>• <code>2:255</code> → فتح الآية مباشرة (وتُقبل الأرقام العربية-الهندية ٢:٢٥٥ أيضاً كمدخل).</div>
            <div>• <code>جذر:رحم</code> → صفحة الجذر وكل مشتقاته.</div>
            <div>• <code>«بسم الله الرحمن الرحيم»</code> → مطابقة العبارة كلماتٍ متتابعة.</div>
            <div>• <code>محمدرسول</code> مع نمط «حروف متصلة» → يجد «مُّحَمَّدٌ رَّسُولُ» رغم اختلاف الكلمات.</div>
            <div>• كل حروف الكلمة روابط: اضغط أي كلمة في النتيجة لعرض جذرها وصيغها ومواضعها.</div>
          </div>
        </details>
      </div>
    </div>`;
  },

  pager(p, count, limit, offset) {
    const pages = Math.ceil(count / limit);
    const cur = Math.floor(offset / limit) + 1;
    if (pages <= 1) return '';
    const mk = (n) => `<button class="chip" data-page="${n}" ${n === cur ? 'style="background:var(--green);color:#fff"' : ''}>${ar(n)}</button>`;
    const list = [];
    for (let i = 1; i <= pages; i++) {
      if (i <= 2 || i > pages - 2 || Math.abs(i - cur) <= 1) list.push(mk(i));
      else if (list[list.length - 1] !== '…') list.push('…');
    }
    return `<div class="card"><div class="chips" style="justify-content:center">
      <button class="chip" data-page="${Math.max(1, cur - 1)}">السابق</button>
      ${list.filter(x => x !== '…').join('')}
      <button class="chip" data-page="${Math.min(pages, cur + 1)}">التالي</button>
      <span class="chip stat">صفحة ${ar(cur)} من ${ar(pages)}</span></div></div>`;
  },

  /* ------------------------------ صفحة الآية ------------------------------ */
  async ayah(main, sura, number) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const [d, g, an] = await Promise.all([API.ayah(sura, number), API.graphAyah(sura, number), API.analysis(sura, number)]);
    const a = d.ayah, s = d.stats;
    const wordsTable = d.words.map(w => `
      <tr data-wordid="${w.id}" style="cursor:pointer">
        <td class="num">${ar(w.number)}</td>
        <td style="font-family:var(--quran-font);font-size:22px">${esc(w.text_uthmani)}</td>
        <td>${esc(w.pos_ar || '—')}</td>
        <td>${w.root_id ? `<span data-root="${w.root_id}" style="cursor:pointer">${esc(w.root_bw)}</span>` : '—'}</td>
        <td class="num">${ar(w.letter_count)}</td>
        <td class="num">${ar(w.diacritic_count)}</td>
        <td class="num">${ar(w.letter_start_ayah)}–${ar(w.letter_start_ayah + w.letter_count - 1)}</td>
        <td class="num">${num(w.letter_start_global)}</td>
        <td class="num">${num(w.abjad)}</td>
      </tr>`).join('');
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المصحف', href: '#/mushaf' },
        { label: `سورة ${a.name_ar}`, href: `#/sura/${sura}` }, { label: `الآية ${ar(number)}` }])}
      <h1 class="page">سورة ${esc(a.name_ar)} — الآية ${ar(number)}</h1>
      <p class="lede">${esc(a.revelation)} · ترتيب النزول ${ar(a.revelation_order)} · الجزء ${ar(a.juz)} ·
        الحزب ${ar(a.hizb)} · الربع ${ar(a.rub)} · الصفحة ${ar(a.page)} · الرُّكوع ${ar(a.ruku)} · المنزل ${ar(a.manzil)}
        ${a.sajda ? ' · <strong>موضع سجدة</strong>' : ''}</p>

      <article class="verse">
        <div class="text">${d.words.map(w => `<span class="w" data-word="w" data-id="${w.id}"
          data-ref="${sura}:${number}" data-n="${w.number}" title="اضغط للتفصيل">${esc(w.text_uthmani)}</span>`).join(' ')}
          <span class="medallion">${ar(number)}</span></div>
        <div class="meta">
          <span class="chip stat">كلمات ${ar(s.words)}</span>
          <span class="chip stat">حروف ${ar(s.letters)}</span>
          <span class="chip stat">محارف ${num(s.chars)}</span>
          <span class="chip stat">حركات ${num(s.diacritics)}</span>
          <span class="chip stat">حروف مختلفة ${ar(s.distinct_letters)}</span>
          <span class="chip stat">حساب الجُمّل ${num(s.abjad)}</span>
          <span class="chip stat">من حروف القرآن ${pct(s.letters_share_of_quran, 4)}</span>
          <span class="chip stat">من كلمات القرآن ${pct(s.words_share_of_quran, 4)}</span>
        </div>
        <div class="actions">
          <button data-prev="${(d.neighbours.prev||{}).sura||''}/${(d.neighbours.prev||{}).number||''}" ${!d.neighbours.prev ? 'disabled' : ''}>الآية السابقة</button>
          <button data-next="${(d.neighbours.next||{}).sura||''}/${(d.neighbours.next||{}).number||''}" ${!d.neighbours.next ? 'disabled' : ''}>الآية التالية</button>
          <button data-audio="${sura}:${number}">تلاوة</button>
          <button data-copy="${esc(a.text_uthmani)}" data-copy-ref="${sura}:${number}">نسخ</button>
          <button data-print>طباعة</button>
        </div>
      </article>

      <div class="card"><h3>جدول الكلمات والمواضع الدقيقة</h3>
        <div class="scroll-x"><table class="tbl">
          <thead><tr><th>#</th><th>الكلمة</th><th>النوع</th><th>الجذر</th><th>الحروف</th><th>الحركات</th>
            <th>موضع الحروف في الآية</th><th>موضع أول حرف في المصحف</th><th>الجُمّل</th></tr></thead>
          <tbody>${wordsTable}</tbody></table></div></div>

      <div class="grid cols-2">
        <div class="card"><h3>توزيع حروف الآية (بعد التوحيد)</h3><div id="lchart" class="chart"></div></div>
        <div class="card"><h3>الحركات والعلامات</h3><div class="scroll-x"><table class="tbl">
          <thead><tr><th>الحركة/العلامة</th><th>العدد</th></tr></thead>
          <tbody>${Object.entries(an.letters.by_diacritic).map(([k, v]) => `<tr><td>${esc(this.diacAr(k))}</td><td class="num">${ar(v)}</td></tr>`).join('')}
          ${an.letters.quran_marks ? `<tr><td>علامات الوقف والرسم</td><td class="num">${ar(an.letters.quran_marks)}</td></tr>` : ''}
          </tbody></table></div></div>
      </div>

      <div class="card"><h3>شبكة علاقات الآية (الكلمات وجذورها)</h3>
        <div class="graphwrap" id="aygraph"></div>
        <div class="note" style="margin-top:10px">العقد الكبيرة: كلمات الآية بترتيبها · الصغيرة الذهبية: جذورها الصرفية.
        اضغط أي جذر لعرض صفحته.</div></div>

      <div class="grid cols-2">
        <div class="card"><h3>الجذور في الآية</h3><div id="rootsbars" class="bars"></div></div>
        <div class="card"><h3>الصيغ المُشتقّة (الوسوم النحوية لكل مقطع)</h3><div id="morph"></div></div>
      </div>`;

    const lt = d.letters.norm_sorted || [];
    Chart.bars(document.getElementById('lchart'), lt.map(([l, c]) => ({ label: l, value: c })), { height: 230, labelSize: 15 });
    Chart.barlist(document.getElementById('rootsbars'), an.roots.map(r => ({ label: r.bw, value: r.count })));
    document.getElementById('morph').innerHTML = `<div class="scroll-x"><table class="tbl">
      <thead><tr><th>الكلمة</th><th>المقاطع (سابقة · جذع · لاحقة)</th></tr></thead>
      <tbody>${d.words.map(w => `<tr><td style="font-family:var(--quran-font);font-size:20px">${esc(w.text_uthmani)}</td>
        <td style="font-size:13px">${(w.segments || []).map(x => `<span class="chip stat" style="margin:2px">${
          x.role === 'STEM' ? 'جذع' : x.role === 'PREFIX' ? 'سابقة' : x.role === 'SUFFIX' ? 'لاحقة' : '—'
        }: ${esc(x.features)}</span>`).join('')}</td></tr>`).join('')}</tbody></table></div>`;
    Graph.ayah(document.getElementById('aygraph'), { nodes: g.nodes, links: g.links }, {});

    // تمييز كلمة معيّنة عند القدوم من نتيجة بحث (‎#/ayah/2/255?w=3‎)
    const want = +((State.read().params.get('w')) || 0);
    if (want) {
      const node = main.querySelector(`.verse .w[data-n="${want}"]`);
      if (node) { node.classList.add('hit'); node.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
    }
  },

  diacAr(name) {
    const map = {
      fatha: 'فتحة', damma: 'ضمة', kasra: 'كسرة', sukun: 'سكون', shadda: 'شدة',
      tanwin_fath: 'تنوين فتح', tanwin_damm: 'تنوين ضم', tanwin_kasr: 'تنوين كسر',
      madda: 'مدة', hamza_above: 'همزة فوق', hamza_below: 'همزة تحت',
      alef_khanjariyya: 'ألف خنجرية', small_high_rounded_zero: 'دائرة صغيرة (۟)',
      small_high_meem: 'ميم صغيرة (ۢ)', small_low_meem: 'ميم صغيرة سفلى',
      small_high_yeh: 'ياء صغيرة', small_high_noon: 'نون صغيرة',
      small_high_upright_rect: 'مستطيل قائم صغير', subscript_alef: 'ألف تحتية',
      empty_centre_low_stop: 'علامة وقف (ۖ)', empty_centre_high_stop: 'علامة وقف (ۗ)',
      rounded_high_stop: 'علامة وقف (ۘ)', small_low_meem_isolated: 'ميم منفصلة صغيرة (ۭ)',
      small_high_dotless_head: 'رأس مهمل صغير (۠)', inverted_damma: 'ضمة مقلوبة', mark_above: 'علامة فوقية',
    };
    return map[name] || name.replace(/^diacritic:/, 'علامة ');
  },

  /* ------------------------------ صفحة الكلمة (وسم) ------------------------------ */
  async tag(main, text) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    let d;
    try { d = await API.tag(text); }
    catch (e) { main.innerHTML = `<div class="empty">${esc(e.message)}<br>جرّب كلمة أخرى أو تحقّق من الإملاء.</div>`; return; }
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'وسوم الكلمات' }, { label: d.tag }])}
      <h1 class="page">الكلمة كوسم: «<span style="font-family:var(--quran-font)">${esc(text)}</span>»</h1>
      <p class="lede">أشكال الكلمة المطبَّعة للبحث: ${d.variants.map(v => `<code>${esc(v)}</code>`).join(' · ')}</p>
      <div class="grid cols-4">
        ${this.tile('عدد المواضع', num(d.count))}
        ${this.tile('أول موضع', d.first.ref, `الكلمة ${num(d.first.word_index)} في المصحف`)}
        ${this.tile('آخر موضع', d.last.ref, `الكلمة ${num(d.last.word_index)} في المصحف`)}
        ${this.tile('متوسط الحروف', ar(d.avg_letter_count))}
        ${this.tile('أقصر فاصل', ar(d.gap_stats.min) + ' كلمة')}
        ${this.tile('أطول فاصل', ar(d.gap_stats.max) + ' كلمة')}
        ${this.tile('متوسط الفاصل', ar(d.gap_stats.avg) + ' كلمة')}
        ${d.root ? this.tile('الجذر', `<span style="font-family:var(--quran-font)">${esc(d.root.arabic)}</span>`, `ورود الجذر ${num(d.root.count)}`) : this.tile('الجذر', '—')}
      </div>
      <div class="grid cols-2">
        <div class="card"><h3>الصيغ المعروضة في المصحف</h3><div class="wordgrid">
          ${d.forms.map(f => `<div class="wordcard" data-tag="${esc(f.text_uthmani)}">
            <div class="t">${esc(f.text_uthmani)}</div><div class="s"><span>${num(f.c)} موضعاً</span></div></div>`).join('')}
        </div></div>
        <div class="card"><h3>التوزيع على السور</h3><div id="sbars" class="bars"></div></div>
      </div>
      <div class="card"><h3>المواضع (${num(Math.min(d.occurrences.length, 1000))} موضعاً)</h3>
        <div class="scroll-x"><table class="tbl"><thead><tr><th>#</th><th>المرجع</th><th>الشكل</th><th>النوع</th><th>موضع الكلمة في الآية</th><th></th></tr></thead>
        <tbody>${d.occurrences.map((o, i) => `<tr><td class="num">${ar(i + 1)}</td>
          <td><a href="#/ayah/${o.ref.split(':')[0]}/${o.ref.split(':')[1]}">${o.ref}</a></td>
          <td style="font-family:var(--quran-font);font-size:21px">${esc(o.text)}</td>
          <td>${esc(o.pos_ar || '—')}</td><td class="num">${ar(o.number_in_ayah)}</td>
          <td><button class="chip" data-wordid="${o.word_id}">تفصيل</button></td></tr>`).join('')}</tbody></table></div></div>
      <div class="card"><h3>شبكة تزامن الكلمة</h3><div class="graphwrap" id="wgraph"></div>
        <div class="note" style="margin-top:10px">الكلمات التي تظهر في الآيات نفسها مع هذه الكلمة — كلما كان الرابط أقوى كان الاجتماع أكثر.</div></div>`;
    if (d.by_sura) Chart.barlist(document.getElementById('sbars'),
      d.by_sura.map(x => ({ label: `${x.name_ar} (${ar(x.sura)})`, value: x.c })));
    try {
      const g = await API.graphWord(text, { limit: 30 });
      Graph.force(document.getElementById('wgraph'), {
        nodes: g.nodes.map(n => ({ id: n.id, label: n.label, count: n.count || 1, level: n.level })),
        links: g.links,
      }, { height: 520, onSelect: (n) => location.hash = '#/tag/' + encodeURIComponent(n.label) });
    } catch (e) { document.getElementById('wgraph').innerHTML = `<div class="empty">لا توجد علاقات كافية</div>`; }
  },

  /* ------------------------------ صفحة الجذر ------------------------------ */
  async rootList(main, roots) {
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'الجذور' }])}
      <h1 class="page">جذور الكلمات</h1>
      <p class="lede">الجذور مستخرجة من المجموعة العربية القرآنية (الصرف) — ${num(roots.length)} جذراً في هذه القائمة.</p>
      <div class="card"><ul class="list">${roots.map(r => `<li data-root="${r.id}">
        <span class="lead" style="font-family:var(--quran-font)">${esc(r.arabic)}</span>
        <span class="mid">${esc(r.bw)}</span>
        <span class="end">${num(r.count)} وروداً · ${ar(r.form_count)} صيغة · ${ar(r.sura_count)} سورة</span></li>`).join('')}</ul></div>`;
  },

  async rootById(main, id) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const d = await API.root(id);
    const r = d.root;
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'الجذور', href: '#/roots' }, { label: r.arabic }])}
      <h1 class="page">الجذر: <span style="font-family:var(--quran-font)">${esc(r.arabic)}</span>
        <span style="font-size:16px;color:var(--ink-faint)">(${esc(r.bw)})</span></h1>
      <div class="grid cols-4">
        ${this.tile('عدد الورود', num(r.count), `نصيب من كلمات القرآن ${pct(d.weighted_share, 3)}`)}
        ${this.tile('عدد الآيات', num(d.ayat_count))}
        ${this.tile('عدد السور', ar(r.sura_count))}
        ${this.tile('عدد الصيغ المشتقة', ar(r.form_count))}
        ${this.tile('عدد الموارد (اللمّات)', ar(r.lemma_count))}
      </div>
      <div class="grid cols-2">
        <div class="card"><h3>الصيغ المشتقة وأكثرها وروداً</h3><div class="wordgrid">
          ${d.forms.slice(0, 40).map(f => `<div class="wordcard" data-tag="${esc(f.text_uthmani)}">
            <div class="t">${esc(f.text_uthmani)}</div>
            <div class="s"><span>${num(f.c)}</span><span>أول ورود ${this.refOf(f.first_ayah)}</span></div></div>`).join('')}
        </div></div>
        <div class="card"><h3>التوزيع على السور</h3><div id="rsuras" class="bars"></div>
          <h3 style="margin-top:16px">الأنماط النحوية</h3><div id="rpos" class="bars"></div></div>
      </div>
      <div class="grid cols-2">
        <div class="card"><h3>الموارد (اللمّات) المشتقة من الجذر</h3>
          <div class="scroll-x"><table class="tbl"><thead><tr><th>الصيغة المعجمية</th><th>الرمز</th><th>النوع</th><th>الورود</th><th>عدد الصيغ</th></tr></thead>
          <tbody>${d.lemmas.map(l => `<tr><td style="font-family:var(--quran-font);font-size:20px">${esc(l.surface_common)}</td>
            <td>${esc(l.bw)}</td><td>${esc(l.pos || '—')}</td><td class="num">${num(l.count)}</td>
            <td class="num">${ar(l.form_count)}</td></tr>`).join('')}</tbody></table></div></div>
        <div class="card"><h3>الجذور المتزامنة (في الآيات نفسها)</h3>
          <div class="scroll-x"><table class="tbl"><thead><tr><th>الجذر</th><th>اجتماع</th><th>إجمالي وروده</th><th></th></tr></thead>
          <tbody>${d.co_roots.slice(0, 25).map(c => `<tr><td style="font-family:var(--quran-font);font-size:20px">${esc(c.arabic)}</td>
            <td class="num">${ar(c.w)}</td><td class="num">${num(c.total)}</td>
            <td><button class="chip" data-root="${c.id}">صفحة الجذر</button></td></tr>`).join('')}</tbody></table></div></div>
      </div>
      <div class="card"><h3>خريطة الجذر الذهنية (جيرانه في المعنى السياقي)</h3><div class="graphwrap" id="mm"></div>
        <div class="note" style="margin-top:10px">اضغط أي عقدة لتوسيع الخريطة حولها.</div></div>`;
    Chart.barlist(document.getElementById('rsuras'),
      d.by_sura.slice(0, 20).map(x => ({ label: `سورة ${ar(x.sura)}`, value: x.c })));
    Chart.barlist(document.getElementById('rpos'), d.pos.map(x => ({ label: x.pos_ar || x.pos, value: x.c })));
    const mm = await API.mindmap({ seed: r.bw, depth: 2, branch: 7 });
    Graph.mindmap(document.getElementById('mm'), mm, { height: 640, onSelect: (label) => this.mindmapNav(label) });
  },

  refOf(wordIdOrAyahId) {
    return '#' + ar(wordIdOrAyahId);
  },
  async mindmapNav(label) {
    const rows = await API.roots({ q: label, limit: 1 });
    if (rows.roots && rows.roots.length) location.hash = `#/root/${rows.roots[0].id}`;
  },

  /* ------------------------------ المصحف ------------------------------ */
  async mushaf(main, params) {
    const suras = (await API.suras()).suras;
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المصحف' }])}
      <h1 class="page">فهرس السور</h1>
      <p class="lede">${ar(114)} سورة · ${num(6236)} آية. اضغط أي سورة لعرض آياتها مع إحصاءات كل آية، وكل كلمة فيها قابلة للنقر.</p>
      <div class="sura-list">${suras.map(s => `
        <div class="sura-card" data-goto="sura/${s.number}">
          <div class="n">${ar(s.number)}</div>
          <div class="nm">${esc(s.name_ar)}</div>
          <div class="mt"><span>${esc(s.revelation)}</span><span>${ar(s.ayah_count)} آية</span>
            <span>${num(s.word_count)} كلمة</span><span>${num(s.letter_count)} حرفاً</span></div>
        </div>`).join('')}</div>`;
  },

  async sura(main, n) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const d = await API.sura(n, true);
    const s = d.sura;
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المصحف', href: '#/mushaf' }, { label: `سورة ${s.name_ar}` }])}
      <h1 class="page">سورة ${esc(s.name_ar)} <span style="font-size:15px;color:var(--ink-faint)">${esc(s.name_translit)} — ${esc(s.name_en)}</span></h1>
      <p class="lede">${esc(s.revelation)} · ترتيب النزول ${ar(s.revelation_order)} · ${ar(s.ayah_count)} آية ·
        ${num(s.word_count)} كلمة · ${num(s.letter_count)} حرفاً · ${num(s.diacritic_count)} حركة ·
        ${ar(s.distinct_letters)} حرفاً مختلفاً · الجزء ${ar(s.juz_start)}–${ar(s.juz_end)} · الصفحة ${ar(s.page_start)}–${ar(s.page_end)}</p>
      <div class="card"><div class="chips" style="justify-content:space-between">
        <span class="chip stat">قيمة الجُمّل للسورة ${num(s.abjad_total)}</span>
        <span class="chip stat">نصيب السورة من حروف القرآن ${pct(s.letter_count / 325386 * 100, 3)}</span>
        <span class="chip stat">نصيبها من كلمات القرآن ${pct(s.word_count / 77433 * 100, 3)}</span>
        <button class="chip" data-graph-sura="${s.number}">شبكة جذور السورة</button>
        <button class="chip" data-print>طباعة</button>
      </div></div>
      ${d.ayat.map(a => `
        <article class="verse">
          <div class="head"><span class="ref" data-goto="${a.sura}/${a.number}">الآية ${ar(a.number)}</span>
            <div class="meta">
              <span class="chip stat">كلمات ${ar(a.word_count)}</span>
              <span class="chip stat">حروف ${ar(a.letter_count)}</span>
              <span class="chip stat">صفحة ${ar(a.page)}</span>
              <span class="chip stat">جزء ${ar(a.juz)}</span>
              ${a.sajda ? '<span class="chip stat">سجدة</span>' : ''}
            </div></div>
          <div class="text" data-ayahtext="${a.sura}:${a.number}">${(a.words || []).length
            ? (a.words || []).map(w => `<span class="w" data-word="w" data-id="${w.id}" data-ref="${a.sura}:${a.number}" data-n="${w.number}">${esc(w.text_uthmani)}</span>`).join(' ') + ` <span class="medallion">${ar(a.number)}</span>`
            : esc(a.text_uthmani) + ` <span class="medallion">${ar(a.number)}</span>`}</div>
          <div class="actions">
            <button data-goto="${a.sura}/${a.number}">التحليل الكامل</button>
            <button data-audio="${a.sura}:${a.number}">تلاوة</button>
            <button data-copy="${esc(a.text_uthmani)}" data-copy-ref="${a.sura}:${a.number}">نسخ</button>
          </div>
        </article>`).join('')}
      <div class="grid cols-2">
        <div class="card"><h3>حروف السورة</h3><div id="sl" class="chart"></div></div>
        <div class="card"><h3>الحركات والعلامات في السورة</h3><div class="scroll-x"><table class="tbl">
          <thead><tr><th>الحركة</th><th>العدد</th></tr></thead><tbody>
          ${d.diacritics.map(x => `<tr><td>${esc(this.diacAr(x.name))}</td><td class="num">${num(x.count)}</td></tr>`).join('')}
          </tbody></table></div></div>
      </div>`;
    Chart.bars(document.getElementById('sl'), d.letters.map(l => ({ label: l.letter, value: l.count })), { height: 230, labelSize: 15 });
  },

  /* ------------------------------ الإحصاءات ------------------------------ */
  async stats(main) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const st = await API.stats();
    const t = st.totals;
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'الإحصاءات' }])}
      <h1 class="page">الإحصاءات الشاملة</h1>
      <p class="lede">كل الأرقام محسوبة مباشرة من النص المفهرس: عدد الآيات والكلمات والحروف والحركات،
        وتوزيعها على الجذور والأنماط النحوية والأجزاء والصفحات، ومتوسطات الطول.</p>
      <div class="grid cols-4">
        ${this.tile('السور', ar(t.suras))}
        ${this.tile('الآيات', num(t.ayahs))}
        ${this.tile('الكلمات', num(t.words))}
        ${this.tile('الحروف', num(t.letters))}
        ${this.tile('الحركات والعلامات الصغيرة', num(t.diacritics))}
        ${this.tile('المحارف الكلية', num(t.chars))}
        ${this.tile('الجذور', num(t.roots))}
        ${this.tile('الموارد الصرفية', num(t.lemmas))}
        ${this.tile('صيغ الكلمات', num(t.distinct_words))}
        ${this.tile('حروف مختلفة', num(t.distinct_letters))}
        ${this.tile('كلمات بجذر', num(t.words_with_root))}
        ${this.tile('كلمات بلا جذر (حروف معنى وضمائر)', num(t.words_without_root))}
      </div>
      <div class="grid cols-4">
        ${this.tile('متوسط الكلمات في الآية', ar(st.averages.words_per_ayah))}
        ${this.tile('متوسط الحروف في الآية', ar(st.averages.letters_per_ayah))}
        ${this.tile('متوسط المحارف في الآية', ar(st.averages.chars_per_ayah))}
        ${this.tile('متوسط الحروف في الكلمة', ar(st.averages.letters_per_word))}
      </div>

      <div class="grid cols-2">
        <div class="card"><h3>تكرار الحروف (الرسم العثماني)</h3><div id="l1" class="chart"></div></div>
        <div class="card"><h3>تكرار الحروف (بعد توحيد الألف والهمزات)</h3><div id="l2" class="chart"></div></div>
      </div>
      <div class="grid cols-2">
        <div class="card"><h3>الحركات والعلامات</h3><div id="dd" class="chart"></div></div>
        <div class="card"><h3>الأنماط النحوية</h3><div id="pd"></div></div>
      </div>
      <div class="grid cols-2">
        <div class="card"><h3>التوزيع على الأجزاء (آيات)</h3><div id="jz" class="chart"></div></div>
        <div class="card"><h3>مكية ومدنية</h3><div id="rv" class="chart"></div>
          <div class="scroll-x" style="margin-top:10px"><table class="tbl"><thead><tr><th>النوع</th><th>آيات</th><th>كلمات</th><th>حروف</th></tr></thead>
          <tbody>${st.revelation.map(r => `<tr><td>${esc(r.revelation)}</td><td class="num">${num(r.ayat)}</td>
            <td class="num">${num(r.words)}</td><td class="num">${num(r.letters)}</td></tr>`).join('')}</tbody></table></div></div>
      </div>
      <div class="card"><h3>أطول الكلمات في المصحف</h3>
        <div class="scroll-x"><table class="tbl"><thead><tr><th>الكلمة</th><th>الحروف</th><th>الموضع</th></tr></thead>
        <tbody>${st.longest_words.map(w => `<tr><td style="font-family:var(--quran-font);font-size:22px">${esc(w.text_uthmani)}</td>
          <td class="num">${ar(w.letter_count)}</td><td><a href="#/ayah/${w.sura}/${w.number}">${w.sura}:${w.number}</a></td></tr>`).join('')}</tbody></table></div></div>
      <div class="card"><h3>مواضع السجد (${ar(st.sajdas.length)})</h3>
        <div class="chips">${st.sajdas.map(s => `<button class="chip" data-goto="${s.sura}/${s.number}">${s.sura}:${s.number} — ${esc(s.sajda_type === 'obligatory' ? 'مؤكدة' : 'مستحبة')}</button>`).join('')}</div></div>
      <div class="card"><h3>أدوات إضافية</h3>
        <div class="row" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
          <div class="field"><label>آيات خالية من حرف</label><input id="wl" maxlength="1" placeholder="م" style="width:80px"></div>
          <button class="chip" id="wlb">اعرض</button>
          <div id="wlout" style="flex:1"></div>
        </div></div>`;
    const byKind = k => (st.letters || []).filter(l => l.kind === k);
    Chart.bars(document.getElementById('l1'), byKind('rasm').slice(0, 17).map(l => ({ label: l.letter, value: l.count })), { height: 250, labelSize: 15 });
    Chart.bars(document.getElementById('l2'), byKind('norm').slice(0, 17).map(l => ({ label: l.letter, value: l.count })), { height: 250, labelSize: 15 });
    Chart.bars(document.getElementById('dd'), st.diacritics.slice(0, 14).map(d => ({ label: this.diacAr(d.name), value: d.count })), { height: 250, labelSize: 9 });
    Chart.barlist(document.getElementById('pd'), st.pos.map(p => ({
      label: p.pos_ar, value: p.count, extra: `${ar(p.word_count)} صيغة` })));
    Chart.bars(document.getElementById('jz'), st.by_juz.map(j => ({ label: ar(j.juz), value: j.ayat })), { height: 240 });
    Chart.donut(document.getElementById('rv'), st.revelation.map(r => ({ label: r.revelation, value: r.ayat })),
      { centerLabel: num(t.ayahs), centerSub: 'آية' });
    document.getElementById('wlb').onclick = async () => {
      const l = document.getElementById('wl').value.trim();
      if (!l) return;
      const r = await API.withoutLetter(l);
      document.getElementById('wlout').innerHTML =
        `<div class="chip stat">${num(r.count)} آية لا تحتوي على «${esc(r.letter)}»</div>
         <div class="chips" style="margin-top:8px">${r.ayat.slice(0, 24).map(a => `<button class="chip" data-goto="${a.sura}/${a.number}">${a.sura}:${a.number}</button>`).join('')}</div>`;
    };
  },

  _ayahNum(id) { return this._ayahNums ? this._ayahNums[id] : id; },

  /* ------------------------------ الشبكات ------------------------------ */
  async graph(main, params) {
    const sura = params.get('sura') || '';
    const minw = params.get('minw') || 12;
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'شبكة الجذور' }])}
      <h1 class="page">شبكة تزامن الجذور</h1>
      <p class="lede">كل عقدة جذر صرفي، وكل خط يعني اجتماع الجذرين في الآية نفسها. حجم العقدة بحسب كثرة ورود الجذر،
        وسماكة الخط بحسب قوة الاجتماع. اضغط أي عقدة لعرض صفحة الجذر، وجرّب التكبير والتحريك.</p>
      <div class="options"><div class="row">
        <div class="field"><label>نطاق: سورة (فارغ = المصحف كله)</label><input id="g-sura" value="${esc(sura)}" placeholder="2"></div>
        <div class="field"><label>أدنى وزن للرابط</label><input id="g-minw" type="number" value="${esc(minw)}" min="1" max="40"></div>
        <button class="chip" id="g-apply" style="background:var(--green);color:#fff">تحديث الشبكة</button>
        <span class="chip stat" id="g-info">…</span>
      </div></div>
      <div class="graphwrap" id="gwrap" style="min-height:660px"></div>`;
    const load = async () => {
      const s = document.getElementById('g-sura').value.trim();
      const mw = document.getElementById('g-minw').value || 12;
      document.getElementById('g-info').textContent = 'جارٍ الحساب…';
      const d = await API.graphRoots({ sura: s || undefined, min_weight: mw, limit_nodes: 60 });
      document.getElementById('g-info').textContent =
        `${ar(d.nodes.length)} جذراً · ${num(d.links.length)} رابطاً · ${num(d.scope.ayahs)} آية في النطاق`;
      Graph.force(document.getElementById('gwrap'), d, { height: 660, onSelect: n => location.hash = '#/root/' + n.id });
      State.write(['graph'], { sura: s, minw: mw });
      return d;
    };
    document.getElementById('g-apply').onclick = load;
    const d = await load();
    // أعلى الأزواج المتزامنة
    const top = d.links.slice().sort((a, b) => b.weight - a.weight).slice(0, 18).map(l => {
      const a = d.nodes.find(n => n.id === l.source || n.id === l.source.id);
      const b = d.nodes.find(n => n.id === l.target || n.id === l.target.id);
      const la = (typeof l.source === 'object' ? l.source : a)?.label || '?';
      const lb = (typeof l.target === 'object' ? l.target : b)?.label || '?';
      return { a: la, b: lb, w: l.weight, pmi: l.pmi };
    });
    const card = el(`<div class="card"><h3>أقوى العلاقات في النطاق</h3>
      <div class="scroll-x"><table class="tbl"><thead><tr><th>الجذر الأول</th><th>الجذر الثاني</th><th>عدد الآيات المشتركة</th><th>قوة الارتباط (PMI)</th></tr></thead>
      <tbody>${top.map(t => `<tr><td style="font-family:var(--quran-font);font-size:20px">${esc(t.a)}</td>
        <td style="font-family:var(--quran-font);font-size:20px">${esc(t.b)}</td>
        <td class="num">${ar(t.w)}</td><td class="num">${ar(t.pmi)}</td></tr>`).join('')}</tbody></table></div></div>`);
    main.appendChild(card);
  },

  async mindmap(main, params) {
    const seed = params.get('seed') || 'rHm';
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'الخريطة الذهنية' }])}
      <h1 class="page">الخريطة الذهنية للجذور</h1>
      <p class="lede">ابدأ من جذر واحد، فتتفرّع حوله الجذور الأكثر تزامناً معه في الآيات، ثم تتفرّع عنها طبقة ثانية.
        كل عقدة قابلة للنقر لتوسيع الخريطة حولها.</p>
      <div class="options"><div class="row">
        <div class="field"><label>الجذر بالبكوولتر (مثال: rHm · Elm · ktb · Hyy)</label><input id="m-seed" value="${esc(seed)}"></div>
        <div class="field"><label>عدد الطبقات</label><select id="m-depth">
          <option value="1">1</option><option value="2" selected>2</option><option value="3">3</option></select></div>
        <div class="field"><label>عدد الفروع لكل عقدة</label><input id="m-branch" type="number" value="7" min="3" max="12"></div>
        <button class="chip" id="m-apply" style="background:var(--green);color:#fff">ارسم الخريطة</button>
        <button class="chip" id="m-rand">جذر عشوائي</button>
      </div></div>
      <div class="graphwrap" id="mmwrap" style="min-height:680px"></div>`;
    const load = async (s) => {
      const seedV = (s || document.getElementById('m-seed').value).trim();
      const depth = +document.getElementById('m-depth').value;
      const branch = +document.getElementById('m-branch').value;
      const d = await API.mindmap({ seed: seedV, depth, branch });
      State.write(['mindmap'], { seed: seedV });
      if (d.error) { document.getElementById('mmwrap').innerHTML = `<div class="empty">${esc(d.error)}</div>`; return; }
      // توزيع الجيران على محيط
      const order = d.nodes.filter(n => n.level > 0);
      const groups = new Map();
      for (const l of d.links) if (d.nodes.find(n => n.id === l.source && n.level === 0)) groups.set(l.target, l.weight);
      order.sort((a, b) => (groups.get(b.id) || 0) - (groups.get(a.id) || 0));
      const perRing = branch;
      order.forEach((n, i) => {
        const ring = Math.floor(i / perRing), within = i % perRing;
        const count = Math.min(perRing, order.length - ring * perRing);
        n.radius = 180 + ring * 150;
        n.angle = (within / count) * Math.PI * 2 + (ring % 2) * 0.4;
      });
      Graph.mindmap(document.getElementById('mmwrap'), d, { height: 680, branch, onSelect: lab => this.mindmapNav(lab) });
    };
    document.getElementById('m-apply').onclick = () => load();
    document.getElementById('m-rand').onclick = async () => {
      const r = await API.roots({ limit: 40, sort: 'count' });
      const pick = r.roots[Math.floor(Math.random() * Math.min(40, r.roots.length))];
      document.getElementById('m-seed').value = pick.bw;
      load(pick.bw);
    };
    await load(seed);
  },

  /* ------------------------------ تفصيل كلمة ------------------------------ */
  async word(main, id) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const d = await API.word(id);
    const w = d.word;
    const a = d.letters || [];
    const marks = (m) => (m || []).map(x => this.diacAr(x)).join(' · ') || '—';
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' },
        { label: `سورة ${esc(w.a_sura ? this._suraName(w.a_sura) : '')}`, href: `#/sura/${w.a_sura}` },
        { label: `الآية ${ar(w.a_number)}`, href: `#/ayah/${w.a_sura}/${w.a_number}` },
        { label: 'تفصيل الكلمة' }])}
      <h1 class="page">تفصيل الكلمة <span style="font-family:var(--quran-font);font-size:38px">${esc(w.text_uthmani)}</span></h1>
      <p class="lede">الكلمة رقم ${ar(w.number)} من ${ar(this._wc(w.ayah_id))} كلمة في الآية ·
        ${esc(this._refLabel(w.a_sura, w.a_number))} ·
        والشكل الإملائي: <code>${esc(w.text_imlaei)}</code> ·
        والصيغة المطبَّعة للبحث: <code>${esc(w.text_norm)}</code></p>
      <div class="grid cols-4">
        ${this.tile('عدد الحروف', ar(w.letter_count))}
        ${this.tile('عدد الحركات', ar(w.diacritic_count))}
        ${this.tile('علامات وقفية داخل الكلمة', ar(w.quran_mark_count))}
        ${this.tile('عدد المحارف', ar(w.char_count))}
        ${this.tile('قيمة الجُمّل', num(w.abjad))}
        ${this.tile('حروف مختلفة في الكلمة', ar(w.distinct_letters))}
        ${this.tile('موضع أول حرف في الآية', ar(w.letter_start_ayah))}
        ${this.tile('موضع أول حرف في المصحف', num(w.letter_start_global))}
        ${this.tile('موضع الكلمة في المصحف', num(w.id), `من ${num(77433)} = ${pct(w.id / 77433 * 100, 4)}`)}
        ${this.tile('وقوع هذه الصيغة', num(d.occurrences_of_form) + ' مرة')}
        ${w.root_id ? this.tile('الجذر', `<span style="font-family:var(--quran-font)">${esc((d.root || {}).arabic || '')}</span>`,
          `<a href="#/root/${w.root_id}">صفحة الجذر</a>`) : this.tile('الجذر', '—')}
        ${this.tile('النوع النحوي', esc(w.pos_ar || '—'), esc(w.pos || ''))}
      </div>

      <div class="card"><h3>حروف الكلمة وحركاتها ومواضعها</h3>
        <div class="letters">
          ${a.map(L => `<div class="letter">
            <div class="g">${esc(L.c)}${(L.marks || []).map(m => `<span style="font-size:15px">${esc(this._markChar(m))}</span>`).join('')}</div>
            <div class="i">حرف ${ar(L.n)}</div>
            <div class="i">الموضع العام ${num(L.global)}</div>
            <div class="i">الجُمّل ${ar(L.abjad)}</div>
          </div>`).join('')}
        </div>
        <div class="scroll-x" style="margin-top:14px"><table class="tbl">
          <thead><tr><th>الحرف</th><th>رقمه في الكلمة</th><th>رقمه في الآية</th><th>رقمه في المصحف</th><th>الحركات عليه</th><th>قيمة الجُمّل</th></tr></thead>
          <tbody>${a.map(L => `<tr><td style="font-family:var(--quran-font);font-size:22px">${esc(L.c)}</td>
            <td class="num">${ar(L.n)}</td><td class="num">${ar(L.in_ayah)}</td><td class="num">${num(L.global)}</td>
            <td>${esc(marks(L.marks))}</td><td class="num">${ar(L.abjad)}</td></tr>`).join('')}</tbody></table></div>
      </div>

      <div class="grid cols-2">
        <div class="card"><h3>التقسيم الصرفي (سابقة · جذع · لاحقة)</h3>
          <div class="scroll-x"><table class="tbl">
            <thead><tr><th>#</th><th>الشكل (بكوولتر)</th><th>الدور</th><th>الوسم</th><th>السمات</th></tr></thead>
            <tbody>${(d.segments || []).map(s => `<tr><td class="num">${ar(s.n)}</td><td>${esc(s.form || '')}</td>
              <td>${s.role === 'STEM' ? 'جذع' : s.role === 'PREFIX' ? 'سابقة' : s.role === 'SUFFIX' ? 'لاحقة'
                    : (s.features === 'MERGED_WITH_PREVIOUS' ? 'مدموجة' : '—')}</td>
              <td>${esc(s.tag || '')}</td><td style="font-size:13px">${esc(s.features || '')}</td></tr>`).join('')}</tbody></table></div>
          ${d.lemma ? `<div class="note" style="margin-top:10px">المورد (اللمة): <strong>${esc(d.lemma.surface_common)}</strong>
            — الصيغة المعجمية ${esc(d.lemma.bw)} — ورودها ${num(d.lemma.count)} مرة من ${ar(d.lemma.form_count)} صيغة.</div>` : ''}
        </div>
        <div class="card"><h3>إحصاء المحارف والحركات</h3>
          <div class="scroll-x"><table class="tbl"><thead><tr><th>الحركة/العلامة</th><th>العدد</th></tr></thead>
            <tbody>${Object.entries(d.stats.by_diacritic || {}).map(([k, v]) =>
              `<tr><td>${esc(this.diacAr(k))}</td><td class="num">${ar(v)}</td></tr>`).join('') ||
              '<tr><td colspan="2">لا حركات على هذه الكلمة</td></tr>'}</tbody></table></div>
          <div class="chips" style="margin-top:12px">
            <button class="chip" data-goto="${w.a_sura}/${w.a_number}">صفحة الآية والتحليل</button>
            <button class="chip" data-tag="${esc(w.text_uthmani)}">الكلمة كوسم</button>
            ${w.root_id ? `<button class="chip" data-root="${w.root_id}">صفحة الجذر</button>` : ''}
            <button class="chip" data-copy="${esc(w.text_uthmani)}" data-copy-ref="${w.a_sura}:${w.a_number}">نسخ</button>
          </div>
        </div>
      </div>`;
  },
  _suraName(n) { return ((this._suras || []).find(s => s.number === n) || {}).name_ar || ('سورة ' + ar(n)); },
  _refLabel(s, a) { return `سورة ${this._suraName(s)} — الآية ${ar(a)}`; },
  _wc(ayahId) { return (this._ayahWordCounts || {})[ayahId] || '?'; },
  _markChar(name) {
    const map = { fatha: '\u064E', damma: '\u064F', kasra: '\u0650', sukun: '\u0652', shadda: '\u0651',
      tanwin_fath: '\u064B', tanwin_damm: '\u064C', tanwin_kasr: '\u064D', madda: '\u0653',
      hamza_above: '\u0654', hamza_below: '\u0655', alef_khanjariyya: '\u0670',
      small_high_rounded_zero: '\u06DF', small_high_meem: '\u06E2', superscript_alef: '\u0670' };
    return map[name] || '';
  },

  /* ------------------------------ نموذج البحث المتقدم ------------------------------ */
  async searchForm(main, params) {
    const st = await API.stats();
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'البحث المتقدم' }])}
      <h1 class="page">البحث المتقدم</h1>
      <p class="lede">اكتب كلمة في شريط البحث أعلى الصفحة، أو استخدم أنماط المطابقة والخيارات والمرشِّحات أدناه.</p>
      ${this.optionsPanel({
        mode: 'word_contains', tashkeel: false, ignore_tashkeel: true, unify_alef: true,
        unify_ya: true, unify_ta: true, ignore_hamza: false, sura: '', juz: '', page_min: '',
        page_max: '', revelation: '', sajda: false, words_min: '', words_max: '',
      }, 0)}
      <div class="grid cols-2">
        <div class="card"><h3>أكثر الكلمات وروداً — اضغط لتصفّح الكلمة كوسم</h3>
          <div class="wordgrid">${st.top_words.slice(0, 24).map(w => `<div class="wordcard" data-tag="${esc(w.text_norm)}">
            <div class="t">${esc(w.text_norm)}</div><div class="s"><span>${num(w.count)} موضعاً</span></div></div>`).join('')}</div></div>
        <div class="card"><h3>أكثر الجذور وروداً — اضغط لصفحة الجذر</h3>
          <div class="wordgrid">${st.top_roots.slice(0, 24).map(r => `<div class="wordcard" data-root="${r.id}">
            <div class="t">${esc(r.arabic)}</div><div class="s"><span>${num(r.count)} وروداً</span></div></div>`).join('')}</div></div>
      </div>
      <div class="card"><h3>تصفّح حسب النمط النحوي</h3>
        <div class="chips">${st.pos.filter(p => p.count > 50).map(p =>
          `<button class="chip" data-goto="pos:${p.pos}">${esc(p.pos_ar)} <span style="color:var(--ink-faint)">${num(p.count)}</span></button>`).join('')}</div></div>`;
  },

  /* ------------------------------ تصفّح حسب النمط النحوي ------------------------------ */
  async pos(main, code) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    const d = await API.posSearch({ pos: code, limit: 200 });
    const meta = await API.pos();
    const row = (meta.pos || []).find(p => p.pos === code) || {};
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'البحث المتقدم', href: '#/search' },
        { label: esc(row.pos_ar || code) }])}
      <h1 class="page">النمط النحوي: ${esc(row.pos_ar || code)}
        <span style="font-size:16px;color:var(--ink-faint)">(${esc(code)})</span></h1>
      <p class="lede">${num(d.count)} كلمة بهذا النمط${row.word_count ? ` من ${ar(row.word_count)} صيغة مختلفة في ${ar(row.sura_count)} سورة` : ''}.
        كل صف قابل للنقر لعرض تفصيل الكلمة وموضعها الدقيق.</p>
      <div class="card"><div class="scroll-x"><table class="tbl">
        <thead><tr><th>#</th><th>المرجع</th><th>الكلمة</th><th>موضع الكلمة في الآية</th><th>الجذر</th><th>الحروف</th><th></th></tr></thead>
        <tbody>${(d.matches || []).map((m, i) => `<tr><td class="num">${ar(i + 1)}</td>
          <td><a href="#/ayah/${m.sura}/${m.number}">${m.sura}:${m.number}</a></td>
          <td style="font-family:var(--quran-font);font-size:21px">${esc(m.text_uthmani)}</td>
          <td class="num">${ar(m.number_in_ayah)}</td>
          <td>${esc(m.root_bw || '—')}</td>
          <td class="num">${ar(m.letter_count)}</td>
          <td><button class="chip" data-wordid="${m.id}">تفصيل</button></td></tr>`).join('')}</tbody>
      </table></div></div>`;
  },

  /* ------------------------------ المحاور الموضوعية ------------------------------ */
  async topics(main) {
    main.innerHTML = `<div class="loading"><span class="spin"></span></div>`;
    let d;
    try { d = await API.topics(); } catch (e) { d = { topics: [] }; }
    const list = d.topics || [];
    if (!list.length) {
      main.innerHTML = `
        ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المحاور الموضوعية' }])}
        <h1 class="page">المحاور الموضوعية</h1>
        <div class="card"><p>لم تُبنَ المحاور بعد. تُستخرج المحاور آلياً من تزامن الجذور في الآيات
          (انتشار الوسوم على مخطط التزامن، مع ترجيح PMI)، ثم تُخزَّن في جدولَي <code>topic</code>
          و<code>topic_root</code> داخل قاعدة البيانات.</p>
          <div class="note">لبنائها: <code>python3 scripts/build_topics.py</code></div></div>`;
      return;
    }
    const totalRoots = list.reduce((a, t) => a + t.size, 0);
    const coverage = d.coverage != null ? d.coverage : 0;
    const shown = list.slice(0, 30);
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المحاور الموضوعية' }])}
      <h1 class="page">المحاور الموضوعية</h1>
      <p class="lede">محاور مستخرجة آلياً من تزامن الجذور: كل جذر يُصانَف مع الجذور التي تكثر
        مشاركتها له الآيات (دمج جشع للأهمية المجتمعية بعد تقليم الحواف بـ PMI)، ويُسمّى المحور
        بأقوى جذوره ربطاً داخله. اضغط أي جذر لعرض صفحته، أو «خريطة المحور» لرسم خريطته الذهنية.</p>
      <div class="grid cols-4">
        ${this.tile('عدد المحاور', ar(list.length))}
        ${this.tile('جذور مصنَّفة', num(totalRoots), d.roots_total ? `من ${num(d.roots_total)}` : '')}
        ${this.tile('نسبة التغطية', coverage ? pct(coverage) : '—')}
        ${this.tile('أكبر محور', `${ar(list[0].size)} جذراً`, esc(list[0].label))}
      </div>
      <div class="card"><h3>أكبر المحاور</h3><div id="tbars" class="bars"></div></div>
      <div class="grid cols-2">
        ${shown.map(t => `
          <div class="card">
            <h3 style="font-family:var(--quran-font);font-size:20px">${esc(t.label)}</h3>
            <div class="meta" style="margin-bottom:10px">
              <span class="chip stat">${ar(t.size)} جذراً</span>
              <span class="chip stat">الوزن ${num(Math.round(t.weight))}</span>
            </div>
            <div class="wordgrid">
              ${(t.roots || []).slice(0, 18).map(r => `<div class="wordcard" data-root="${r.id}">
                <div class="t">${esc(r.arabic)}</div>
                <div class="s"><span>${num(r.count)} وروداً</span></div></div>`).join('')}
            </div>
            ${(t.roots || []).length > 18 ? `<div class="note" style="margin-top:8px">
              و${ar((t.roots || []).length - 18)} جذراً آخر — <a href="#/root/${(t.roots[18] || {}).id}">تصفّح</a></div>` : ''}
            ${(t.roots || []).length ? `<div class="chips" style="margin-top:12px">
              <button class="chip" data-mindmap="${esc((t.roots[0] || {}).bw || '')}">خريطة المحور</button>
              <button class="chip" data-root="${(t.roots[0] || {}).id}">صفحة أبرز جذر</button>
            </div>` : ''}
          </div>`).join('')}
      </div>
      ${list.length > shown.length ? `<div class="note" style="margin-top:14px">
        يُعرض أكبر ${ar(shown.length)} محوراً من ${ar(list.length)} — صغّر
        <code>--max-size</code> أو ارفع <code>--resolution</code> لتحاور أدق.</div>` : ''}`;
    Chart.barlist(document.getElementById('tbars'),
      list.slice(0, 14).map(t => ({ label: t.label, value: t.size, extra: `الوزن ${Math.round(t.weight)}` })));
  },

  /* ------------------------------ المصادر ------------------------------ */
  async about(main) {
    const m = await this.meta();
    main.innerHTML = `
      ${this.crumbs([{ label: 'الرئيسية', href: '#/' }, { label: 'المصادر والمنهج' }])}
      <h1 class="page">المصادر والمنهج</h1>
      <div class="card"><h2>مصادر النص</h2>
        <ul class="list">
          <li><span class="lead">تنزيل</span><span class="mid">${esc(m.sources.tanzil)}</span>
            <span class="end"><a href="https://tanzil.net" target="_blank">tanzil.net</a></span></li>
          <li><span class="lead">الصرف</span><span class="mid">${esc(m.sources.corpus)}</span>
            <span class="end"><a href="https://corpus.quran.com" target="_blank">corpus.quran.com</a></span></li>
          <li><span class="lead">الميتاداتا</span><span class="mid">${esc(m.sources.metadata)}</span>
            <span class="end">تنزيل</span></li>
          <li><span class="lead">الخطوط</span><span class="mid">KFGQPC Uthmanic Hafs (مجمع الملك فهد) · Amiri Quran · IBM Plex Sans Arabic · Reem Kufi · Aref Ruqaa — كلها مفتوحة الترخيص (OFL/KFGQPC-Free)</span><span class="end">محزّمة محلياً</span></li>
        </ul>
      </div>
      <div class="card"><h2>كيف يعمل البحث</h2>
        <ol>
          <li>يُطبَّع النص والاستعلام بنفس الدالة: حذف التشكيل وعلامات الوقف والكشيدة، وتوحيد الألف والياء والتاء المربوطة (قابلة للتعطيل خياراً بخيار).</li>
          <li>تُفهرَس لكل كلمة ثلاث نسخ رسم: الرسم العثماني مع حذف الألف الخنجرية (ٱلْكِتَٰبِ ← الكتب)، والرسم العثماني مع جعلها ألفاً (← الكتاب)، والشكل الإملائي (ٱلصَّلَوٰةَ ← الصلاة). فأي طريقة كتابة يكتبها الباحث تصل إلى الكلمة نفسها.</li>
          <li>المطابقة تُجرى على مستوى الحروف مع خرائط مواضع دقيقة، فيُستخرج لكل نتيجة: رقم الكلمة في الآية، موضع أول حرف في الآية وفي المصحف كاملاً، الجزء والحزب والربع والمنزل والرُّكوع والصفحة، وحساب الجُمّل.</li>
          <li>خيار «احترام التشكيل» يُلزم الحركات التي كتبها الباحث فقط؛ ما لم يكتبه لا يُشترط.</li>
          <li>الجذور والموارد والأنماط النحوية من المجموعة العربية القرآنية، مع محاذاة محرفية مُتحقَّق منها آلياً على كل آية (${num(m.totals.ayahs)} آية، صفر كلمة غير مرتبطة).</li>
        </ol>
      </div>
      <div class="card"><h2>تحقّق من الأرقام</h2>
        <div class="grid cols-4">
          ${this.tile('الآيات', num(m.totals.ayahs))}
          ${this.tile('الكلمات', num(m.totals.words))}
          ${this.tile('الحروف', num(m.totals.letters))}
          ${this.tile('الجذور', num(m.totals.roots))}
        </div>
        <div class="note" style="margin-top:12px">قاعدة البيانات تحمل بصمات SHA-256 لكل ملف مصدر، ويمكن إعادة بنائها كاملة بالأمر:
          <code>python3 scripts/build_db.py</code></div>
      </div>
      <div class="card"><h2>واجهة البرمجة</h2>
        <p>كل ما في الواجهة متاح عبر واجهة برمجية موثّقة: <a href="/api/docs">/api/docs</a></p>
        <ul class="list">
          <li><span class="mid"><code>/api/search</code></span><span class="end">البحث بكل الأنماط والخيارات والمرشِّحات</span></li>
          <li><span class="mid"><code>/api/ayah/{s}/{a}</code></span><span class="end">الآية مع كل كلماتها ومواضعها</span></li>
          <li><span class="mid"><code>/api/stats/analysis/{s}/{a}</code></span><span class="end">تحليل نصّي تفصيلي للآية</span></li>
          <li><span class="mid"><code>/api/root/{id}</code> · <code>/api/lemma/{id}</code></span><span class="end">الجذور والموارد</span></li>
          <li><span class="mid"><code>/api/graph/roots</code> · <code>/api/graph/mindmap</code></span><span class="end">الشبكات والخريطة الذهنية</span></li>
        </ul>
      </div>`;
  },
};
