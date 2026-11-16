"""
engine.py — محرك البحث والتحليل
================================
يبني فهارس في الذاكرة من قاعدة البيانات:
  • مجرى الحروف (letter stream) لِلكتاب كاملاً مع خرائط مواضع دقيقة لكل محرف
    → كل مطابقة تُترجم فوراً إلى: السورة، الآية، رقم الكلمة، موضع الحرف،
      الموضع العالمي للحرف والكلمة، الجزء/الحزب/الربع/الصفحة.
  • مجرى النص المشكول (للتوافق الحساس للتشكيل).
مطبَّع الاستعلام بنفس دالة تطبيع النص المفهرس ⇒ لا نتائج ضائعة ولا مطابقات زائفة.
"""
from __future__ import annotations

import functools
import re
import sqlite3
import threading
from array import array
from dataclasses import dataclass, field

from .arabic import (
    NormOptions, classify, diacritic_name, has_diacritics, letters_only,
    matches_with_tashkeel, normalize, text_stats,
)

WORD_SEP = "\x1f"          # فاصل الكلمات في المجرى
AYAH_SEP = "\x1e"          # (يُستعمل لحساب حدود الآيات عند العرض)


@dataclass
class Filters:
    sura: list[int] | None = None
    juz: list[int] | None = None
    hizb: list[int] | None = None
    page_min: int | None = None
    page_max: int | None = None
    revelation: str | None = None          # مكية | مدنية
    sajda: bool | None = None
    words_min: int | None = None
    words_max: int | None = None
    letters_min: int | None = None
    letters_max: int | None = None
    pos: list[str] | None = None
    root_id: int | None = None
    lemma_id: int | None = None
    word_pos_in_ayah: str | None = None     # first | middle | last

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}


@dataclass
class Match:
    word_ids: list[int]
    spans: list[tuple[int, int]] = field(default_factory=list)   # مواضع في المجرى
    letter_positions: list[int] = field(default_factory=list)    # الموضع العالمي للحروف


class QuranEngine:
    """محرك بحث القرآن: بحث متقدم + إحصاءات + شبكات علاقات."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._build_streams()
        self._static = {}
        self._prepare_static()

    # ------------------------------------------------------------------
    # الاتصال بقاعدة البيانات (اتصال لكل خيط)
    # ------------------------------------------------------------------
    @property
    def db(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA temp_store=MEMORY")
            self._local.conn = conn
        return conn

    def q(self, sql: str, args: tuple | list = ()) -> list[sqlite3.Row]:
        return self.db.execute(sql, args).fetchall()

    # ------------------------------------------------------------------
    # بناء مجاري الفهرسة
    # ------------------------------------------------------------------
    def _build_streams(self) -> None:
        """
        بناء مجرى الفهرسة: لكل كلمة تُضاف ثلاثة "خانات" (نُسخ رسم):
          0) الرسم العثماني بعد إسقاط الألف الخنجرية        (ٱلْكِتَٰبِ → الكتب)
          1) الرسم العثماني مع جعل الألف الخنجرية ألفاً     (ٱلْكِتَٰبِ → الكتاب)
          2) الشكل الإملائي الكامل                           (ٱلصَّلَوٰةَ → الصلاة)
        كل الخانات تُشير إلى الكلمة نفسها، فيُصاب الهدف بأي طريقة كتابة يكتبها
        الباحث. تُخزَّن أيضاً خرائط: موضع المحرف ← الكلمة، ورقم الحرف داخل النسخة.
        مجرى ثانٍ بلا فواصل (letters_across) لمطابقة سلاسل الحروف عبر الكلمات.
        """
        rows = self.q("""SELECT id, sura, ayah_id, number, text_uthmani, text_imlaei,
                                text_bare, letter_count, letter_start_ayah,
                                letter_start_global
                         FROM word ORDER BY id""")
        self.words = rows
        n = len(rows)
        wid_arr = array("i", [0] * n)
        sura_arr = array("i", [0] * n)
        ayah_arr = array("i", [0] * n)
        num_arr = array("i", [0] * n)

        chars: list[str] = []
        char_word = array("i")
        char_lin = array("i")          # رقم الحرف داخل النسخة (1..)
        char_var = array("b")          # 0=عثماني، 1=عثماني+خنجرية، 2=إملائي
        flat: list[str] = []
        flat_word = array("i")
        flat_lin = array("i")

        for i, r in enumerate(rows):
            wid_arr[i] = r["id"]
            sura_arr[i] = r["sura"]
            ayah_arr[i] = r["ayah_id"]
            num_arr[i] = r["number"]
            u1 = normalize(r["text_uthmani"], NormOptions(khanjariyya_as_alef=False))
            u2 = normalize(r["text_uthmani"], NormOptions(khanjariyya_as_alef=True))
            im = normalize(r["text_imlaei"] or "", NormOptions(khanjariyya_as_alef=True))
            variants = [u1] + ([u2] if u2 != u1 else []) + ([im] if im and im != u1 and im != u2 else [])
            for var_id, vtext in enumerate(variants):
                chars.append(WORD_SEP)
                char_word.append(-1)
                char_lin.append(-1)
                char_var.append(-1)
                k = 0
                for ch in vtext:
                    if classify(ch) != "letter":
                        continue
                    k += 1
                    chars.append(ch)
                    char_word.append(i)
                    char_lin.append(k)
                    char_var.append(var_id)
            # المجرى المتصل (بلا فواصل) من النسخة العثمانية مع إسقاط الخنجرية
            k = 0
            for ch in u1:
                if classify(ch) != "letter":
                    continue
                k += 1
                flat.append(ch)
                flat_word.append(i)
                flat_lin.append(k)
        chars.append(WORD_SEP)
        char_word.append(-1)
        char_lin.append(-1)
        char_var.append(-1)

        self.stream = "".join(chars)
        self.char_word = char_word
        self.char_lin = char_lin
        self.char_var = char_var
        self.flat_stream = "".join(flat)
        self.flat_word = flat_word
        self.flat_lin = flat_lin
        self.word_ids = wid_arr
        self._w_sura, self._w_ayah, self._w_num = sura_arr, ayah_arr, num_arr

        idx: dict[int, list[int]] = {}
        for i, a in enumerate(self._w_ayah):
            idx.setdefault(a, []).append(i)
        self.ayah_word_idx = idx
        sur: dict[int, list[int]] = {}
        for i, s in enumerate(self._w_sura):
            sur.setdefault(s, []).append(i)
        self.sura_word_idx = sur
        # نسخة مطبَّعة من حروف الكلمة العثمانية (لتصحيح مواضع المطابقات الإملائية)
        self._u1_cache: dict[int, str] = {}

    def _prepare_static(self) -> None:
        self._static["totals"] = {r["key"]: r["value"] for r in self.q("SELECT key,value FROM meta")}
        self._static["suras"] = [dict(r) for r in self.q("SELECT * FROM sura ORDER BY number")]
        self._static["letter_global"] = [dict(r) for r in
                                        self.q("SELECT * FROM letter_global ORDER BY kind, rank")]
        self._static["pos_stat"] = [dict(r) for r in
                                    self.q("SELECT * FROM pos_stat ORDER BY count DESC")]
        self._static["diacritic_global"] = [
            dict(r) for r in self.q("""SELECT name, SUM(count) AS count FROM ayah_diacritic
                                       GROUP BY name ORDER BY count DESC""")]

    # ------------------------------------------------------------------
    # البحث
    # ------------------------------------------------------------------
    def _phrase_pattern(self, q: str, mode: str) -> re.Pattern:
        esc = re.escape(q)
        if mode == "word_exact":
            return re.compile(f"(?<={WORD_SEP}){esc}(?={WORD_SEP})")
        if mode == "word_prefix":
            return re.compile(f"(?<={WORD_SEP}){esc}")
        if mode == "word_suffix":
            return re.compile(f"{esc}(?={WORD_SEP})")
        if mode == "word_contains":
            # داخل الكلمة فقط (لا يعبر حدود الكلمات)
            return re.compile(f"(?<={WORD_SEP})[^{WORD_SEP}]*{esc}[^{WORD_SEP}]*(?={WORD_SEP})")
        if mode == "exact_letters":
            # كل حروف الكلمة بالترتيب تماماً مهما كان ترتيبها الداخلي ممتداً
            return re.compile(f"(?<={WORD_SEP}){esc}(?={WORD_SEP})")
        return re.compile(esc)          # anywhere: متتالية حروف في أي موضع

    def search(
        self, q: str, mode: str = "word_contains", opts: NormOptions | None = None,
        filters: Filters | None = None, tashkeel_sensitive: bool = False,
        limit: int = 200, offset: int = 0, proximity: int = 0,
        return_stats: bool = True,
    ) -> dict:
        """
        البحث الرئيسي.
        mode: word_exact | word_prefix | word_suffix | word_contains | anywhere | phrase
        tashkeel_sensitive: مطابقة تُلزم حركات الاستعلام
        proximity: للعبارات — أقصى عدد كلمات فاصلة بين كلمتين متتاليتين
        """
        opts = opts or NormOptions()
        q = (q or "").strip()
        if not q:
            return {"query": q, "count": 0, "matches": [], "stats": {}}

        tokens = q.split()
        if mode == "phrase" or len(tokens) > 1:
            hits = self._search_phrase(tokens, opts, filters, tashkeel_sensitive,
                                      proximity, mode="word_exact" if mode == "phrase" else mode)
        else:
            hits = self._search_single(tokens[0], mode, opts, filters, tashkeel_sensitive)

        total = len(hits)
        page = hits[offset:offset + limit] if len(hits) > limit else hits
        out = {
            "query": q, "mode": mode, "count": total,
            "offset": offset, "limit": limit,
            "normalized": normalize(q, opts),
            "matches": [self.hit_to_json(h, opts) for h in page],
        }
        if return_stats and hits:
            out["stats"] = self.hits_stats(hits)
        return out

    def _filter_sql(self, filters: Filters | None) -> tuple[str, list]:
        if not filters:
            return "", []
        where, args = [], []
        f = filters
        if f.sura:
            where.append(f"a.sura IN ({','.join('?' * len(f.sura))})"); args += f.sura
        if f.juz:
            where.append(f"a.juz IN ({','.join('?' * len(f.juz))})"); args += f.juz
        if f.hizb:
            where.append(f"a.hizb IN ({','.join('?' * len(f.hizb))})"); args += f.hizb
        if f.page_min is not None:
            where.append("a.page >= ?"); args.append(f.page_min)
        if f.page_max is not None:
            where.append("a.page <= ?"); args.append(f.page_max)
        if f.revelation:
            where.append("s.revelation = ?"); args.append(f.revelation)
        if f.sajda is not None:
            where.append("a.sajda = ?"); args.append(1 if f.sajda else 0)
        if f.words_min is not None:
            where.append("a.word_count >= ?"); args.append(f.words_min)
        if f.words_max is not None:
            where.append("a.word_count <= ?"); args.append(f.words_max)
        if f.letters_min is not None:
            where.append("a.letter_count >= ?"); args.append(f.letters_min)
        if f.letters_max is not None:
            where.append("a.letter_count <= ?"); args.append(f.letters_max)
        sql = (" AND " + " AND ".join(where)) if where else ""
        return sql, args

    def _filtered_words(self, filters: Filters | None) -> set[int] | None:
        """مجموعة فهارس الكلمات المسموح بها حسب المرشِّحات (None = الكل)"""
        if not filters:
            return None
        f = filters
        if not any([f.sura, f.juz, f.hizb, f.page_min, f.page_max, f.revelation,
                    f.sajda, f.words_min, f.words_max, f.letters_min, f.letters_max]):
            return None
        sql, args = self._filter_sql(f)
        rows = self.q(f"""SELECT a.id FROM ayah a JOIN sura s ON s.number=a.sura WHERE 1=1 {sql}""", args)
        allowed_ayah = {r["id"] for r in rows}
        return {i for i, a in enumerate(self._w_ayah) if a in allowed_ayah}

    def _word_index_filter(self, allowed: set[int] | None, i: int) -> bool:
        return allowed is None or i in allowed

    def _search_single(self, token: str, mode: str, opts: NormOptions,
                       filters: Filters | None, tashkeel_sensitive: bool) -> list[Match]:
        """
        البحث عن كلمة واحدة.
        tashkeel_sensitive: تُلزَم الحركات التي كتبها المستخدم — أي حركة في الاستعلام
        يجب أن توجد على الحرف نفسه في الكلمة (استعلام بلا حركات = مطابقة عادية).
        mode='letters_across': سلسلة حروف متصلة قد تمتد على أكثر من كلمة في الآية.
        """
        from .arabic import has_diacritics
        if mode == "letters_across":
            return self._search_across(token, opts, filters)
        variants = self._query_variants(token, opts)
        hits: list[Match] = []
        allowed = self._filtered_words(filters)
        seen: set[int] = set()
        require_marks = tashkeel_sensitive and has_diacritics(token)
        for nq in variants:
            for m in self._phrase_pattern(nq, mode).finditer(self.stream):
                wi = self.char_word[m.start()]
                if wi < 0 or not self._word_index_filter(allowed, wi):
                    continue
                if wi in seen:
                    continue
                if require_marks and not matches_with_tashkeel(
                        self.words[wi]["text_uthmani"], token):
                    continue
                seen.add(wi)
                hits.append(Match([self.word_ids[wi]], [(m.start(), m.end())],
                                  [self._letter_pos(wi, m.start())]))
        # ترتيب النتائج بترتيب المصحف دائماً (فهرس الكلمة العالمي)
        hits.sort(key=lambda m: m.word_ids[0])
        return hits

    # ------------------------------------------------------------------
    # حلّ الوسوم إلى معرّفات كلمات
    # ------------------------------------------------------------------
    @staticmethod
    def _chunks(seq: list, size: int = 900):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    def resolve_word_ids(self, text: str, opts: NormOptions | None = None,
                         mode: str = "word_exact") -> list[int]:
        """
        معرّفات الكلمات التي يطابقها الوسم، بمطابقة رسم-واعية للتشكيل:
        يُجرَّب المطابقة التامة أولاً، ثم المطابقة الجزئية (ضمن الكلمة) إن لم توجد.
        """
        opts = opts or NormOptions()
        hits = self._search_single(text, mode, opts, None, False)
        if not hits and mode == "word_exact":
            hits = self._search_single(text, "word_contains", opts, None, False)
        return sorted({h.word_ids[0] for h in hits})

    def _word_rows_by_ids(self, ids: list[int], columns: str = "*") -> list[sqlite3.Row]:
        """جلب صفوف الكلمات على دفعات (تفادي حدّ عدد المتغيّرات في SQLite)."""
        out: list[sqlite3.Row] = []
        for part in self._chunks(ids):
            ph = ",".join("?" * len(part))
            out += self.q(f"SELECT {columns} FROM word WHERE id IN ({ph}) ORDER BY id", part)
        return out

    def _letter_pos(self, wi: int, stream_pos: int) -> int:
        """
        الموضع العالمي للحرف الأول من المطابقة.
        النسخ العثمانية (0/1): الموضع دقيق مباشرة. النسخة الإملائية (2): تُحاذى
        حروفها مع حروف الرسم العثماني للكلمة نفسها لاستخراج الموضع الصحيح.
        """
        lin = self.char_lin[stream_pos]
        var = self.char_var[stream_pos]
        r = self.words[wi]
        if var in (0, 1):
            return r["letter_start_global"] + lin - 1
        u1 = self._u1_cache.get(wi)
        if u1 is None:
            u1 = letters_only(normalize(r["text_uthmani"],
                                        NormOptions(khanjariyya_as_alef=False)))
            self._u1_cache[wi] = u1
        im = letters_only(normalize(r["text_imlaei"] or "",
                                    NormOptions(khanjariyya_as_alef=True)))
        if im == u1 or not u1:
            return r["letter_start_global"] + lin - 1
        import difflib
        sm = difflib.SequenceMatcher(a=im, b=u1, autojunk=False)
        target = max(lin - 1, 0)
        j = None
        for op, a1, a2, b1, b2 in sm.get_opcodes():
            if op == "equal" and a1 <= target < a2:
                j = b1 + (target - a1)
                break
        if j is None:
            for op, a1, a2, b1, b2 in sm.get_opcodes():
                if a1 <= target < a2:
                    j = min(b1, max(len(u1) - 1, 0))
                    break
        if j is None:
            j = min(target, max(len(u1) - 1, 0))
        return r["letter_start_global"] + j

    def _search_across(self, token: str, opts: NormOptions,
                       filters: Filters | None) -> list[Match]:
        """سلاسل الحروف المتصلة (قد تمتد على كلمتين أو أكثر داخل الآية الواحدة)."""
        variants = self._query_variants(token, opts)
        allowed = self._filtered_words(filters)
        out: list[Match] = []
        seen: set[tuple[int, int]] = set()
        for nq in variants:
            if len(nq) < 2:
                continue
            for m in re.finditer(re.escape(nq), self.flat_stream):
                i0, i1 = self.flat_word[m.start()], self.flat_word[m.end() - 1]
                if i0 < 0 or i1 < 0 or (i0, i1) in seen:
                    continue
                if not all(self._word_index_filter(allowed, k) for k in range(i0, i1 + 1)):
                    continue
                if self._w_ayah[i0] != self._w_ayah[i1]:
                    continue
                seen.add((i0, i1))
                wids = [self.word_ids[k] for k in range(i0, i1 + 1)]
                out.append(Match(wids, [(m.start(), m.end())],
                                 [self.words[i0]["letter_start_global"]
                                  + self.flat_lin[m.start()] - 1]))
        return out

    def _query_variants(self, token: str, opts: NormOptions) -> list[str]:
        """كل الأشكال المطبَّعة للاستعلام: تضمن مطابقة الرسم العثماني والإملائي."""
        from .arabic import search_variants
        base = search_variants(token, opts)
        extra = []
        for v in base:
            extra.append(v)
        # نسخة بلا همزات (توسيع اختياري): تُضاف فقط إذا كان الاستعلام يحوي همزة
        if any(c in token for c in "أإآٱؤئء"):
            sk = normalize(token, NormOptions(strip_hamza=True, unify_alef=opts.unify_alef,
                                              unify_ya=opts.unify_ya,
                                              unify_ta_marbuta=opts.unify_ta_marbuta))
            if sk not in extra:
                extra.append(sk)
        return extra

    def _search_phrase(self, tokens: list[str], opts: NormOptions, filters: Filters | None,
                       tashkeel_sensitive: bool, proximity: int, mode: str = "word_exact") -> list[Match]:
        per_token = [self._search_single(t, mode, opts, filters, tashkeel_sensitive)
                     for t in tokens]
        if not per_token or any(not p for p in per_token):
            return []
        # بناء خرائط: كلمة → موضعها في ترتيب الكلمات العالمي
        pos_of = {}
        for p in per_token:
            for m in p:
                pos_of[m.word_ids[0]] = self._word_pos(m.word_ids[0])
        out: list[Match] = []
        first = per_token[0]
        cand_index = {m.word_ids[0]: m for m in first}
        for m0 in first:
            ids = [m0.word_ids[0]]
            spans = list(m0.spans)
            letters = list(m0.letter_positions)
            p0 = pos_of[ids[0]]
            ok = True
            for k in range(1, len(per_token)):
                found = None
                for cand in per_token[k]:
                    cid = cand.word_ids[0]
                    pc = pos_of[cid]
                    if pc > p0 and pc - p0 <= 1 + proximity and self._same_ayah(ids[0], cid):
                        found = cand
                        # تحقّق: هل الترتيب متزايد
                        p0 = pc
                        break
                if found is None:
                    ok = False
                    break
                ids.append(found.word_ids[0])
                spans += found.spans
                letters += found.letter_positions
            if ok:
                out.append(Match(ids, spans, letters))
        return out

    def _word_pos(self, word_id: int) -> int:
        """موضع الكلمة في ترتيب كلمات المصحف = معرّفها (تصاعدي مع الترتيب)"""
        return word_id

    def _same_ayah(self, w1: int, w2: int) -> bool:
        i1 = w1 - 1
        i2 = w2 - 1
        if not (0 <= i1 < len(self._w_ayah) and 0 <= i2 < len(self._w_ayah)):
            return False
        return self._w_ayah[i1] == self._w_ayah[i2]

    # ------------------------------------------------------------------
    # تحويل النتائج إلى JSON
    # ------------------------------------------------------------------
    def hit_to_json(self, m: Match, opts: NormOptions | None = None,
                    context: bool = True) -> dict:
        first = m.word_ids[0]
        i = first - 1
        sura, ayah_id = self._w_sura[i], self._w_ayah[i]
        row = self.q("""SELECT a.*, s.name_ar, s.name_translit, s.revelation
                        FROM ayah a JOIN sura s ON s.number=a.sura WHERE a.id=?""", (ayah_id,))[0]
        # رقم الآية داخل السورة من جدول الآيات — لا من موضع الكلمة داخل الآية (كان يُفسد جميع المراجع)
        num = row["number"]
        words = self.q("""SELECT id,number,text_uthmani,text_imlaei,letter_count,
                                 letter_start_ayah,letter_start_global,root_bw,lemma_bw,
                                 pos,pos_ar FROM word WHERE ayah_id=? ORDER BY number""", (ayah_id,))
        matched = set(m.word_ids)
        out = {
            "sura": sura,
            "sura_name": row["name_ar"],
            "ayah": num,
            "ayah_id": ayah_id,
            "ref": f"{sura}:{num}",
            "ref_ar": f"سورة {row['name_ar']} — الآية {num}",
            "text_uthmani": row["text_uthmani"],
            "text_imlaei": row["text_imlaei"],
            "positions": {
                "juz": row["juz"], "hizb": row["hizb"], "rub": row["rub"],
                "manzil": row["manzil"], "ruku": row["ruku"], "page": row["page"],
                "sajda": bool(row["sajda"]), "sajda_type": row["sajda_type"],
                "ayah_in_quran": ayah_id, "ayah_in_sura": num,
                "words_in_ayah": row["word_count"],
                "letters_in_ayah": row["letter_count"],
                "chars_in_ayah": row["char_count"],
                "diacritics_in_ayah": row["diacritic_count"],
                "distinct_letters_in_ayah": row["distinct_letters"],
                "abjad_value": row["abjad_total"],
                "ayah_text_share_letters": round(row["letter_count"] / 325386 * 100, 4),
            },
            "matched_words": [],
            "stats": {
                "word_count": row["word_count"], "letter_count": row["letter_count"],
                "char_count": row["char_count"], "abjad_total": row["abjad_total"],
            },
        }
        for w in words:
            if w["id"] in matched:
                out["matched_words"].append({
                    "word_id": w["id"], "number_in_ayah": w["number"],
                    "text": w["text_uthmani"], "imlaei": w["text_imlaei"],
                    "letters": w["letter_count"],
                    "letter_start_in_ayah": w["letter_start_ayah"],
                    "letter_start_in_quran": w["letter_start_global"],
                    "root": w["root_bw"], "lemma": w["lemma_bw"],
                    "pos": w["pos"], "pos_ar": w["pos_ar"],
                    "position_in_ayah": ("الأولى" if w["number"] == 1 else
                                         "الأخيرة" if w["number"] == row["word_count"] else
                                         "وسطى"),
                })
        if context:
            out["words"] = [{"n": w["number"], "t": w["text_uthmani"],
                             "l": w["letter_count"], "m": w["id"] in matched} for w in words]
        return out

    def hits_stats(self, hits: list[Match]) -> dict:
        """إحصاءات المواضع للنتائج: توزيع على السور/الأجزاء/الأحزاب/الصفحات/المواضع"""
        word_ids = [m.word_ids[0] for m in hits]
        if not word_ids:
            return {}
        suf = ",".join("?" * len(word_ids))
        by_sura = self.q(f"""SELECT w.sura, s.name_ar, COUNT(*) c FROM word w
                             JOIN sura s ON s.number=w.sura WHERE w.id IN ({suf})
                             GROUP BY w.sura ORDER BY c DESC""", word_ids)
        by_juz = self.q(f"""SELECT a.juz, COUNT(*) c FROM word w JOIN ayah a ON a.id=w.ayah_id
                            WHERE w.id IN ({suf}) GROUP BY a.juz ORDER BY a.juz""", word_ids)
        by_hizb = self.q(f"""SELECT a.hizb, COUNT(*) c FROM word w JOIN ayah a ON a.id=w.ayah_id
                             WHERE w.id IN ({suf}) GROUP BY a.hizb ORDER BY c DESC LIMIT 12""", word_ids)
        by_page = self.q(f"""SELECT a.page, COUNT(*) c FROM word w JOIN ayah a ON a.id=w.ayah_id
                             WHERE w.id IN ({suf}) GROUP BY a.page ORDER BY a.page LIMIT 20""", word_ids)
        by_rev = self.q(f"""SELECT s.revelation, COUNT(*) c FROM word w
                            JOIN sura s ON s.number=w.sura WHERE w.id IN ({suf})
                            GROUP BY s.revelation""", word_ids)
        pos_dist = self.q(f"""SELECT w.pos, w.pos_ar, COUNT(*) c FROM word w
                              WHERE w.id IN ({suf}) GROUP BY w.pos ORDER BY c DESC LIMIT 12""", word_ids)
        by_pos = self.q(f"""SELECT CASE WHEN w.number=1 THEN 'أول الآية'
                                       WHEN w.number=(SELECT word_count FROM ayah WHERE id=w.ayah_id)
                                       THEN 'آخر الآية' ELSE 'وسط الآية' END AS place,
                                  COUNT(*) c FROM word w WHERE w.id IN ({suf}) GROUP BY place""", word_ids)
        ayat = self.q(f"""SELECT COUNT(DISTINCT w.ayah_id) c FROM word w WHERE w.id IN ({suf})""",
                      word_ids)[0]["c"]
        suras_n = self.q(f"""SELECT COUNT(DISTINCT w.sura) c FROM word w WHERE w.id IN ({suf})""",
                         word_ids)[0]["c"]
        first_w = self.q("""SELECT w.id,w.sura,a.number AS ayah FROM word w
                            JOIN ayah a ON a.id=w.ayah_id WHERE w.id=?""", (min(word_ids),))[0]
        last_w = self.q("""SELECT w.id,w.sura,a.number AS ayah FROM word w
                           JOIN ayah a ON a.id=w.ayah_id WHERE w.id=?""", (max(word_ids),))[0]
        return {
            "occurrences": len(word_ids),
            "ayat": ayat, "suras": suras_n,
            "ayat_ratio": round(ayat / 6236 * 100, 4),
            "first_occurrence": {"ref": f"{first_w['sura']}:{first_w['ayah']}",
                                 "word_index_in_quran": first_w["id"],
                                 "share_before": round(first_w["id"] / 77433 * 100, 4)},
            "last_occurrence": {"ref": f"{last_w['sura']}:{last_w['ayah']}",
                                "word_index_in_quran": last_w["id"],
                                "share_after": round((77433 - last_w["id"]) / 77433 * 100, 4)},
            "span_words": last_w["id"] - first_w["id"],
            "by_sura": [dict(r) for r in by_sura],
            "by_juz": [dict(r) for r in by_juz],
            "by_hizb": [dict(r) for r in by_hizb],
            "by_page": [dict(r) for r in by_page],
            "by_revelation": [dict(r) for r in by_rev],
            "by_pos": [dict(r) for r in pos_dist],
            "by_place_in_ayah": [dict(r) for r in by_pos],
        }

    # ------------------------------------------------------------------
    # البحث بالجذور والموارد والأنماط الصرفية
    # ------------------------------------------------------------------
    def roots(self, q: str = "", limit: int = 100, sort: str = "count") -> list[dict]:
        sql = "SELECT * FROM root"
        args: list = []
        if q:
            sql += " WHERE arabic LIKE ? OR bw LIKE ?"
            args = [f"%{normalize(q)}%", f"%{q}%"]
        order = {"count": "count DESC", "alpha": "arabic", "forms": "form_count DESC"}
        sql += f" ORDER BY {order.get(sort, 'count DESC')} LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.q(sql, args)]

    def lemmas_for_root(self, root_id: int) -> list[dict]:
        return [dict(r) for r in self.q(
            "SELECT * FROM lemma WHERE root_id=? ORDER BY count DESC", (root_id,))]

    def word_graph(self, text: str, limit: int = 25, min_weight: int = 1,
                   opts: NormOptions | None = None) -> dict:
        """
        شبكة تزامن الكلمة: الكلمات التي تظهر في الآيات نفسها مع الكلمة المطلوبة.
        تُجمَّع الجيران بصيغتها المطبَّعة (فيجتمع «قَالُوا» و«قالوا» في عقدة واحدة)،
        والوزن = عدد الآيات المشتركة (تُحسب مرة واحدة لكل آية).
        """
        opts = opts or NormOptions()
        ids = self.resolve_word_ids(text, opts)
        if not ids:
            return {"found": False, "word": text, "nodes": [], "links": []}
        shared: dict[str, set] = {}
        label: dict[str, str] = {}
        for part in self._chunks(ids):
            ph = ",".join("?" * len(part))
            for r in self.q(f"""SELECT w2.text_norm AS tn, w2.text_uthmani AS tu, w1.ayah_id AS aid
                                FROM word w1 JOIN word w2
                                  ON w2.ayah_id = w1.ayah_id AND w2.id <> w1.id
                                WHERE w1.id IN ({ph})""", part):
                shared.setdefault(r["tn"], set()).add(r["aid"])
                bare = self._bare_norm(r["tu"])
                prev = label.get(r["tn"])
                if prev is None or len(bare) < len(prev):
                    label[r["tn"]] = bare
        ranked = sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ranked = [(tn, len(ay)) for tn, ay in ranked if len(ay) >= min_weight][:limit]
        if not ranked:
            return {"found": True, "word": text, "count": len(ids), "nodes": [], "links": []}
        freq = {r["text_norm"]: r["count"] for r in self.q(
            "SELECT text_norm, count FROM word_freq")}
        nodes = [{"id": "seed", "label": text, "count": len(ids), "level": 0, "pos": None}]
        links = []
        for tn, w in ranked:
            label_txt = label.get(tn) or tn
            nodes.append({"id": tn, "label": label_txt, "count": w, "weight": w,
                          "freq": freq.get(tn, w), "level": 1})
            links.append({"source": "seed", "target": tn, "weight": w})
        return {"found": True, "word": text, "count": len(ids),
                "nodes": nodes, "links": links, "metric": "الآيات المشتركة",
                "note": f"أكثر {len(ranked)} كلمة تزامناً مع الوسم في الآيات"}

    def _bare_norm(self, text_uthmani: str) -> str:
        """الشكل المعروض للجار: الرسم العثماني منزوع العلامات ليبقى صافياً للحساب."""
        try:
            return letters_only(normalize(text_uthmani, NormOptions(strip_tashkeel=True)))
        except Exception:
            return text_uthmani

    def root_page(self, root_id: int) -> dict:
        r = self.q("SELECT * FROM root WHERE id=?", (root_id,))
        if not r:
            return {}
        root = dict(r[0])
        lemmas = self.lemmas_for_root(root_id)
        forms = self.q("""SELECT text_uthmani, text_imlaei, text_norm, COUNT(*) c,
                                 MIN(ayah_id) first_ayah
                          FROM word WHERE root_id=? GROUP BY text_uthmani
                          ORDER BY c DESC LIMIT 60""", (root_id,))
        by_sura = self.q("""SELECT sura, COUNT(*) c FROM word WHERE root_id=?
                            GROUP BY sura ORDER BY c DESC""", (root_id,))
        ayat = self.q("SELECT COUNT(DISTINCT ayah_id) c FROM word WHERE root_id=?", (root_id,))[0]["c"]
        pos = self.q("""SELECT pos, pos_ar, COUNT(*) c FROM word WHERE root_id=?
                        GROUP BY pos ORDER BY c DESC""", (root_id,))
        derived = self.q("""SELECT tag, COUNT(*) c FROM (
                              SELECT json_extract(value,'$.tag') tag FROM word, json_each(word.segments)
                              WHERE root_id=?) GROUP BY tag ORDER BY c DESC""", (root_id,))
        co = self.co_occurring_roots(root_id, limit=40)
        return {
            "root": root, "lemmas": lemmas,
            "forms": [dict(r) for r in forms],
            "by_sura": [dict(r) for r in by_sura],
            "pos": [dict(r) for r in pos],
            "derivation_types": [dict(r) for r in derived],
            "ayat_count": ayat, "occurrences": root["count"],
            "co_roots": co,
            "weighted_share": round(root["count"] / 77433 * 100, 4),
        }

    def lemma_page(self, lemma_id: int) -> dict:
        r = self.q("SELECT * FROM lemma WHERE id=?", (lemma_id,))
        if not r:
            return {}
        lemma = dict(r[0])
        forms = self.q("""SELECT text_uthmani, COUNT(*) c, MIN(ayah_id) first_ayah,
                                 MAX(ayah_id) last_ayah
                          FROM word WHERE lemma_id=? GROUP BY text_uthmani
                          ORDER BY c DESC""", (lemma_id,))
        by_sura = self.q("SELECT sura, COUNT(*) c FROM word WHERE lemma_id=? GROUP BY sura ORDER BY c DESC",
                         (lemma_id,))
        feats = self.q("""SELECT json_extract(value,'$.tag') tag, COUNT(*) c
                          FROM word, json_each(word.segments) WHERE lemma_id=?
                          GROUP BY tag ORDER BY c DESC""", (lemma_id,))
        return {"lemma": lemma, "forms": [dict(x) for x in forms],
                "by_sura": [dict(x) for x in by_sura],
                "grammar": [dict(x) for x in feats]}

    def pos_search(self, pos: list[str], filters: Filters | None = None,
                   limit: int = 200, offset: int = 0) -> dict:
        sql_f, args = self._filter_sql(filters)
        ph = ",".join("?" * len(pos))
        rows = self.q(f"""SELECT w.id FROM word w JOIN ayah a ON a.id=w.ayah_id
                          JOIN sura s ON s.number=a.sura
                          WHERE w.pos IN ({ph}) {sql_f} ORDER BY w.id LIMIT ? OFFSET ?""",
                      list(pos) + args + [limit, offset])
        total = self.q(f"""SELECT COUNT(*) c FROM word w JOIN ayah a ON a.id=w.ayah_id
                           JOIN sura s ON s.number=a.sura WHERE w.pos IN ({ph}) {sql_f}""",
                       list(pos) + args)[0]["c"]
        hits = [Match([r["id"]], [], []) for r in rows]
        return {"count": total, "matches": [self.hit_to_json(h) for h in hits]}

    # ------------------------------------------------------------------
    # الكلمة كوسم: صفحة الوسم
    # ------------------------------------------------------------------
    def word_tag(self, text: str, opts: NormOptions | None = None) -> dict:
        opts = opts or NormOptions()
        variants = self._query_variants(text, opts)
        # حلّ الوسم عبر مجاري الحروف (لا عبر تطابق الشكل المطبَّع وحده)، فيصيب
        # «الصلاة» الكلمات «ٱلصَّلَوٰةَ» رغم اختلاف الرسم.
        ids = self.resolve_word_ids(text, opts)
        if not ids:
            return {"found": False, "query": text, "variants": variants}
        rows = self._word_rows_by_ids(ids, """id, sura, ayah_id, number, text_uthmani,
                 text_imlaei, letter_count, letter_start_global, root_bw, lemma_bw, pos, pos_ar""")
        def qids(sql_tpl: str) -> list[sqlite3.Row]:
            out: list[sqlite3.Row] = []
            for part in self._chunks(ids):
                ph = ",".join("?" * len(part))
                out += self.q(sql_tpl.format(ph=ph), part)
            return out
        by_sura = qids("""SELECT w.sura, s.name_ar, COUNT(*) c FROM word w
                             JOIN sura s ON s.number=w.sura WHERE w.id IN ({ph})
                             GROUP BY w.sura ORDER BY c DESC, w.sura""")
        forms = qids("""SELECT text_uthmani, COUNT(*) c FROM word WHERE id IN ({ph})
                           GROUP BY text_uthmani ORDER BY c DESC""")
        # إحصاء التوزيع: أول/آخر موضع ومتوسط الحروف والفجوات بين المواضع
        first_id, last_id = ids[0], ids[-1]
        avg_letters = (sum(r["letter_count"] for r in rows) / len(rows)) if rows else 0.0
        g = [b - a for a, b in zip(ids, ids[1:])]
        root = self.q("SELECT * FROM root WHERE id=?",
                      (self.q("SELECT id FROM root WHERE bw=?", (rows[0]["root_bw"],))[0]["id"],)) \
            if rows[0]["root_bw"] else []
        return {
            "found": True, "query": text, "variants": variants,
            "tag": normalize(text, opts),
            "count": len(ids),
            "forms": [dict(r) for r in forms],
            "by_sura": [dict(r) for r in by_sura],
            "first": {"word_index": first_id, "ref": self._ref_for_word(first_id)},
            "last": {"word_index": last_id, "ref": self._ref_for_word(last_id)},
            "avg_letter_count": round(avg_letters, 2),
            "gap_stats": {"min": min(g) if g else 0, "max": max(g) if g else 0,
                          "avg": round(sum(g) / len(g), 2) if g else 0},
            "root": dict(root[0]) if root else None,
            "occurrences": [{"word_id": r["id"], "ref": self._ref_for_word(r["id"]),
                             "text": r["text_uthmani"], "pos": r["pos"], "pos_ar": r["pos_ar"],
                             "number_in_ayah": r["number"]} for r in rows[:1000]],
        }

    def _ref_for_word(self, word_id: int) -> str:
        r = self.q("""SELECT w.sura, a.number FROM word w JOIN ayah a ON a.id=w.ayah_id
                      WHERE w.id=?""", (word_id,))
        return f"{r[0]['sura']}:{r[0]['number']}" if r else "?"

    # ------------------------------------------------------------------
    # شبكات العلاقات (الخريطة الذهنية)
    # ------------------------------------------------------------------
    def co_occurring_roots(self, root_id: int, limit: int = 40, min_weight: int = 2) -> list[dict]:
        """الجذور التي تجتمع مع هذا الجذر في الآيات نفسها (مرتَّبة بعدد الاجتماع)."""
        rows = self.q("""
            SELECT r2.root_id AS id, rt.arabic, rt.bw, COUNT(*) AS w, rt.count AS total
            FROM root_ayah r1
            JOIN root_ayah r2 ON r2.ayah_id = r1.ayah_id AND r2.root_id <> r1.root_id
            JOIN root rt ON rt.id = r2.root_id
            WHERE r1.root_id = ?
            GROUP BY r2.root_id
            HAVING w >= ?
            ORDER BY w DESC, total DESC
            LIMIT ?""", (root_id, min_weight, limit))
        return [dict(r) for r in rows]

    def root_graph(self, scope: dict | None = None, min_weight: int = 3,
                   limit_nodes: int = 120, metric: str = "cooc") -> dict:
        """شبكة تزامن الجذور: عقد = جذور، حواف = اجتماعها في الآية (مع PMI اختياري)"""
        scope = scope or {}
        where, args = "", []
        if scope.get("sura"):
            where += " AND sura = ?"; args.append(int(scope["sura"]))
        if scope.get("juz"):
            where += " AND ayah_id IN (SELECT id FROM ayah WHERE juz=?)"; args.append(int(scope["juz"]))
        if scope.get("sura_from") and scope.get("sura_to"):
            where += " AND sura BETWEEN ? AND ?"; args += [int(scope["sura_from"]), int(scope["sura_to"])]
        rows = self.q(f"""SELECT root_id, ayah_id FROM root_ayah WHERE 1=1 {where}""", args)
        from collections import Counter
        ayah_roots: dict[int, list[int]] = {}
        for r in rows:
            ayah_roots.setdefault(r["ayah_id"], []).append(r["root_id"])
        pair: Counter = Counter()
        deg: Counter = Counter()
        for _a, roots in ayah_roots.items():
            u = sorted(set(roots))
            for x in range(len(u)):
                deg[u[x]] += 1
                for y in range(x + 1, len(u)):
                    pair[(u[x], u[y])] += 1
        n_ayah = max(len(ayah_roots), 1)
        top_nodes = set(x for x, _ in deg.most_common(limit_nodes))
        links = []
        for (a, b), w in pair.items():
            if a in top_nodes and b in top_nodes and w >= min_weight:
                links.append((a, b, w))
        links.sort(key=lambda x: -x[2])
        links = links[:6000]
        info = {r["id"]: dict(r) for r in self.q("SELECT id,arabic,bw,count FROM root")}
        nodes = []
        for rid in top_nodes:
            if rid not in info:
                continue
            nodes.append({"id": rid, "label": info[rid]["arabic"], "bw": info[rid]["bw"],
                          "count": info[rid]["count"], "ayat_in_scope": deg[rid],
                          "freq_in_scope": round(deg[rid] / n_ayah * 100, 2)})
        return {"nodes": nodes,
                "links": [{"source": a, "target": b, "weight": w,
                           "pmi": round(self._pmi(w, deg[a], deg[b], n_ayah), 3),
                           "jaccard": round(w / max(deg[a] + deg[b] - w, 1), 4)}
                          for a, b, w in links],
                "scope": {"ayahs": n_ayah, "roots_in_scope": len(deg), **scope},
                "metric": metric}

    @staticmethod
    def _pmi(w: int, ca: int, cb: int, n: int) -> float:
        import math
        if w <= 0 or ca <= 0 or cb <= 0:
            return 0.0
        p = w / n
        return math.log(p / ((ca / n) * (cb / n)) + 1e-12, 2)

    def mindmap(self, seed: str, depth: int = 2, branch: int = 8,
                mode: str = "root", scope: dict | None = None) -> dict:
        """خريطة ذهنية شعاعية: العقدة المركزية ثم الأقرب تزامناً، ثم الجيران"""
        scope = scope or {}
        where, args = "", []
        if scope.get("sura"):
            where += " AND sura = ?"; args.append(int(scope["sura"]))
        if scope.get("juz"):
            where += " AND ayah_id IN (SELECT id FROM ayah WHERE juz=?)"; args.append(int(scope["juz"]))
        rows = self.q(f"SELECT root_id, ayah_id FROM root_ayah WHERE 1=1 {where}", args)
        from collections import Counter, defaultdict
        co: dict[int, Counter] = defaultdict(Counter)
        freq: Counter = Counter()
        for r in rows:
            freq[r["root_id"]] += 1
        ayah_roots: dict[int, set] = defaultdict(set)
        for r in rows:
            ayah_roots[r["ayah_id"]].add(r["root_id"])
        for _a, roots in ayah_roots.items():
            for x in roots:
                for y in roots:
                    if x != y:
                        co[x][y] += 1
        # تحديد البذرة: جذر بالرمز أو بالعربية
        seed_row = None
        if mode == "root":
            seed_row = self.q("SELECT id,arabic,bw,count FROM root WHERE bw=? OR arabic=?",
                              (seed, normalize(seed)))[0:1]
        if not seed_row:
            return {"nodes": [], "links": [], "error": "لم يُعثر على البذرة"}
        s = dict(seed_row[0])
        nodes = {s["id"]: {"id": s["id"], "label": s["arabic"], "level": 0,
                           "count": s["count"], "freq_in_scope": freq[s["id"]]}}
        links: list[dict] = []
        frontier = [s["id"]]
        for level in range(1, depth + 1):
            nxt = []
            for node in frontier:
                for nb, w in co[node].most_common(branch):
                    if nb in nodes:
                        continue
                    info = self.q("SELECT arabic,count FROM root WHERE id=?", (nb,))[0]
                    nodes[nb] = {"id": nb, "label": info["arabic"], "level": level,
                                 "count": info["count"], "freq_in_scope": freq[nb]}
                    nxt.append(nb)
                    links.append({"source": node, "target": nb, "weight": w,
                                  "coh": round(w / max(freq[node], 1), 3)})
            frontier = nxt
        return {"nodes": list(nodes.values()), "links": links, "seed": s,
                "scope": {"ayahs": len(ayah_roots), **scope}}

    def ayah_graph(self, sura: int, number: int) -> dict:
        """شبكة علاقات الآية: كلماتها، جذورها، وأدوارها النحوية"""
        a = self.q("SELECT * FROM ayah WHERE sura=? AND number=?", (sura, number))
        if not a:
            return {}
        ayah_id = a[0]["id"]
        words = self.q("""SELECT id,number,text_uthmani,root_id,root_bw,lemma_bw,pos,pos_ar
                          FROM word WHERE ayah_id=? ORDER BY number""", (ayah_id,))
        roots = {w["root_id"]: w["root_bw"] for w in words if w["root_id"]}
        root_rows = {}
        if roots:
            ph = ",".join("?" * len(roots))
            for r in self.q(f"SELECT id,arabic,bw,count FROM root WHERE id IN ({ph})",
                            list(roots.keys())):
                root_rows[r["id"]] = dict(r)
        nodes = [{"id": f"w{w['id']}", "label": w["text_uthmani"], "type": "word",
                  "pos": w["pos_ar"], "pos_code": w["pos"], "root": w["root_bw"],
                  "n": w["number"], "letters": None} for w in words]
        nodes += [{"id": f"r{rid}", "label": rr["arabic"], "type": "root",
                   "count": rr["count"]} for rid, rr in root_rows.items()]
        links = []
        for i in range(len(words) - 1):
            links.append({"source": f"w{words[i]['id']}", "target": f"w{words[i+1]['id']}",
                          "rel": "تتابع", "kind": "sequence"})
        for w in words:
            if w["root_id"] in root_rows:
                links.append({"source": f"w{w['id']}", "target": f"r{w['root_id']}",
                              "rel": "من جذر", "kind": "root"})
        return {"ayah": {"sura": sura, "number": number, "text": a[0]["text_uthmani"],
                         "stats": {k: a[0][k] for k in
                                   ("word_count", "letter_count", "char_count",
                                    "diacritic_count", "distinct_letters", "abjad_total")}},
                "nodes": nodes, "links": links,
                "roots": [dict(r) for r in root_rows.values()]}

    # ------------------------------------------------------------------
    # الإحصاءات
    # ------------------------------------------------------------------
    def overview(self) -> dict:
        t = dict(self._static["totals"])
        sura_stats = self.q("""SELECT number,name_ar,ayah_count,word_count,letter_count
                               FROM sura""")
        biggest = self.q("SELECT sura,number,word_count,letter_count FROM ayah ORDER BY word_count DESC LIMIT 5")
        smallest = self.q("SELECT sura,number,word_count,letter_count FROM ayah ORDER BY word_count ASC LIMIT 5")
        longest_words = self.q("""SELECT text_uthmani, letter_count, sura, ayah_id, number FROM word
                                  ORDER BY letter_count DESC LIMIT 10""")
        avg = self.q("""SELECT AVG(word_count) aw, AVG(letter_count) al, AVG(char_count) ac,
                               AVG(diacritic_count) ad FROM ayah""")[0]
        return {
            "totals": t,
            "averages": {"words_per_ayah": round(avg["aw"], 3),
                         "letters_per_ayah": round(avg["al"], 3),
                         "chars_per_ayah": round(avg["ac"], 3),
                         "diacritics_per_ayah": round(avg["ad"], 3),
                         "letters_per_word": round(int(t["letters"]) / int(t["words"]), 3)},
            "longest_ayat": [dict(r) for r in biggest],
            "shortest_ayat": [dict(r) for r in smallest],
            "longest_words": [dict(r) for r in longest_words],
            "letters": [r for r in self._static["letter_global"]],
            "diacritics": self._static["diacritic_global"],
            "pos": self._static["pos_stat"],
            "top_roots": [dict(r) for r in self.q("SELECT id,arabic,count,form_count,sura_count FROM root ORDER BY count DESC LIMIT 30")],
            "top_words": [dict(r) for r in self.q("SELECT text_norm,count,sura_count FROM word_freq ORDER BY count DESC LIMIT 30")],
            "revelation": [dict(r) for r in self.q("""SELECT s.revelation, COUNT(*) ayat,
                              SUM(a.word_count) words, SUM(a.letter_count) letters
                              FROM ayah a JOIN sura s ON s.number=a.sura
                              GROUP BY s.revelation""")],
            "by_juz": [dict(r) for r in self.q("""SELECT juz, COUNT(*) ayat, SUM(word_count) words,
                              SUM(letter_count) letters FROM ayah GROUP BY juz ORDER BY juz""")],
            "sajdas": [dict(r) for r in self.q("""SELECT sura,number,sajda_type FROM ayah
                              WHERE sajda=1 ORDER BY sura,number""")],
            "suras": [dict(r) for r in sura_stats],
        }

    def letters_for_ayah(self, ayah_id: int) -> dict:
        rows = self.q("SELECT kind,letter,count FROM ayah_letter WHERE ayah_id=?", (ayah_id,))
        out = {"rasm": {}, "norm": {}}
        for r in rows:
            out[r["kind"]][r["letter"]] = r["count"]
        out["rasm_sorted"] = sorted(out["rasm"].items(), key=lambda x: -x[1])
        out["norm_sorted"] = sorted(out["norm"].items(), key=lambda x: -x[1])
        return out

    def letter_index(self) -> dict:
        return {"rasm": [r for r in self._static["letter_global"] if r["kind"] == "rasm"],
                "norm": [r for r in self._static["letter_global"] if r["kind"] == "norm"]}

    def ayat_without_letter(self, letter: str, limit: int = 50) -> dict:
        l = normalize(letter)
        rows = self.q("""SELECT a.sura, a.number, a.word_count, a.letter_count
                         FROM ayah a WHERE NOT EXISTS (
                           SELECT 1 FROM ayah_letter al WHERE al.ayah_id=a.id
                             AND al.kind='norm' AND al.letter=?)
                         ORDER BY a.id LIMIT ?""", (l, limit))
        total = self.q("""SELECT COUNT(*) c FROM ayah a WHERE NOT EXISTS (
                            SELECT 1 FROM ayah_letter al WHERE al.ayah_id=a.id
                              AND al.kind='norm' AND al.letter=?)""", (l,))[0]["c"]
        return {"letter": l, "count": total, "ayat": [dict(r) for r in rows]}

    def word_detail(self, word_id: int) -> dict:
        w = self.q("""SELECT w.*, a.sura AS a_sura, a.number AS a_number, a.text_uthmani AS a_text
                      FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE w.id=?""", (word_id,))
        if not w:
            return {}
        w = dict(w[0])
        segs = []
        import json as _json
        try:
            segs = _json.loads(w["segments"] or "[]")
        except Exception:
            segs = []
        for s in segs:
            s["pos_ar"] = None
        st = text_stats(w["text_uthmani"])
        letters = []
        pos_in_word = 0
        for ch in w["text_uthmani"]:
            if classify(ch) == "letter":
                pos_in_word += 1
                letters.append({"c": ch, "n": pos_in_word,
                                "global": w["letter_start_global"] + pos_in_word - 1,
                                "in_ayah": w["letter_start_ayah"] + pos_in_word - 1,
                                "abjad": None, "marks": []})
            elif classify(ch) == "diacritic" and letters:
                letters[-1]["marks"].append(diacritic_name(ch))
        from .arabic import ABJAD
        for L in letters:
            L["abjad"] = ABJAD.get(L["c"], 0)
        root = self.q("SELECT * FROM root WHERE id=?", (w["root_id"],))[0:1]
        lemma = self.q("SELECT * FROM lemma WHERE id=?", (w["lemma_id"],))[0:1]
        return {"word": w, "segments": segs, "letters": letters,
                "stats": st.as_dict(),
                "root": dict(root[0]) if root else None,
                "lemma": dict(lemma[0]) if lemma else None,
                "share_of_quran": round(1 / 77433 * 100, 6),
                "occurrences_of_form": self.q("SELECT COUNT(*) c FROM word WHERE text_norm=?",
                                              (w["text_norm"],))[0]["c"]}

    def random_ayah(self) -> dict:
        r = self.q("SELECT sura, number FROM ayah ORDER BY RANDOM() LIMIT 1")[0]
        return self.ayah_page(r["sura"], r["number"])

    def ayah_page(self, sura: int, number: int) -> dict:
        a = self.q("""SELECT a.*, s.name_ar, s.name_translit, s.name_en, s.revelation,
                             s.revelation_order FROM ayah a JOIN sura s ON s.number=a.sura
                      WHERE a.sura=? AND a.number=?""", (sura, number))
        if not a:
            return {}
        a = dict(a[0])
        words = []
        for w in self.q("""SELECT * FROM word WHERE ayah_id=? ORDER BY number""", (a["id"],)):
            wd = dict(w)
            import json as _json
            wd["segments"] = _json.loads(wd["segments"] or "[]")
            st = text_stats(wd["text_uthmani"])
            wd["letters_breakdown"] = st.as_dict()
            words.append(wd)
        return {"ayah": a, "words": words,
                "letters": self.letters_for_ayah(a["id"]),
                "stats": {
                    "words": a["word_count"], "letters": a["letter_count"],
                    "chars": a["char_count"], "diacritics": a["diacritic_count"],
                    "distinct_letters": a["distinct_letters"], "abjad": a["abjad_total"],
                    "letters_share_of_quran": round(a["letter_count"] / 325386 * 100, 5),
                    "words_share_of_quran": round(a["word_count"] / 77433 * 100, 5),
                },
                "neighbours": {"prev": self._neighbour(sura, number, -1),
                               "next": self._neighbour(sura, number, +1)}}

    def _neighbour(self, sura: int, number: int, d: int) -> dict | None:
        if d < 0:
            r = self.q("""SELECT sura,number FROM ayah WHERE (sura<?) OR (sura=? AND number<?)
                          ORDER BY sura DESC, number DESC LIMIT 1""", (sura, sura, number))
        else:
            r = self.q("""SELECT sura,number FROM ayah WHERE (sura>?) OR (sura=? AND number>?)
                          ORDER BY sura ASC, number ASC LIMIT 1""", (sura, sura, number))
        return dict(r[0]) if r else None

    def sura_page(self, n: int, with_words: bool = False) -> dict:
        s = self.q("SELECT * FROM sura WHERE number=?", (n,))
        if not s:
            return {}
        ayat = [dict(r) for r in self.q("""SELECT id,sura,number,text_uthmani,text_imlaei,
                                                  word_count,letter_count,char_count,
                                                  diacritic_count,distinct_letters,abjad_total,
                                                  juz,hizb,rub,manzil,ruku,page,sajda
                                           FROM ayah WHERE sura=? ORDER BY number""", (n,))]
        if with_words:
            # كلمات السورة كلها في استعلام واحد (لتجنّب مئات الطلبات من الواجهة)
            by_ayah: dict[int, list[dict]] = {}
            for r in self.q("""SELECT id, ayah_id, number, text_uthmani, text_imlaei, letter_count,
                                      letter_start_ayah, letter_start_global, root_id, root_bw, pos_ar
                               FROM word WHERE sura=? ORDER BY id""", (n,)):
                d = dict(r)
                by_ayah.setdefault(d["ayah_id"], []).append(d)
            for a in ayat:
                a["words"] = by_ayah.get(a["id"], [])
        return {"sura": dict(s[0]), "ayat": ayat,
                "letters": [dict(r) for r in self.q(
                    "SELECT letter,count FROM sura_letter WHERE kind='norm' AND sura=?", (n,))],
                "diacritics": [dict(r) for r in self.q(
                    "SELECT name,count FROM sura_diacritic WHERE sura=? ORDER BY count DESC", (n,))]}

    def compare_words(self, w1: str, w2: str) -> dict:
        out = {}
        for k, w in (("a", w1), ("b", w2)):
            t = self.word_tag(w)
            out[k] = {"query": w, "count": t.get("count", 0),
                      "by_sura": t.get("by_sura", [])[:20],
                      "first": t.get("first"), "last": t.get("last")}
        return out


def normalize_root_label(bw: str) -> str:
    from .arabic import buckwalter_to_arabic
    return buckwalter_to_arabic(bw, keep_marks=False)
