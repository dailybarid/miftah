"""
main.py — واجهة برمجة محرك بحث القرآن الكريم (FastAPI)
=====================================================
نقاط النهاية كلها ترجع JSON (وبعضها HTML للصفحات).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .arabic import NormOptions, abjad_value, letters_only, normalize, text_stats
from .engine import Filters, QuranEngine

ROOT = Path(__file__).resolve().parent.parent
DB = os.environ.get("QURAN_DB", str(ROOT / "data" / "quran.db"))
WEB = ROOT / "web"

app = FastAPI(
    title="محرك بحث القرآن الكريم",
    description="محرك بحث وتحليل للقرآن الكريم: بحث دقيق بالتشكيل، جذور وموارد صرفية، "
                "إحصاءات الحروف والمواضع، وشبكات علاقات وخريطة ذهنية.",
    version="1.0.0",
    docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

_engine: QuranEngine | None = None


def engine() -> QuranEngine:
    global _engine
    if _engine is None:
        if not os.path.exists(DB):
            raise HTTPException(503, "قاعدة البيانات غير مبنية. شغّل: python3 scripts/build_db.py")
        _engine = QuranEngine(DB)
    return _engine


def opts_from_query(
    ignore_tashkeel: bool = True, unify_alef: bool = True, unify_ya: bool = True,
    unify_ta: bool = True, ignore_hamza: bool = False,
) -> NormOptions:
    return NormOptions(
        strip_tashkeel=ignore_tashkeel, unify_alef=unify_alef, unify_ya=unify_ya,
        unify_ta_marbuta=unify_ta, strip_hamza=ignore_hamza,
    )


def filters_from_query(
    sura: str | None = None, juz: str | None = None, hizb: str | None = None,
    page_min: int | None = None, page_max: int | None = None,
    revelation: str | None = None, sajda: bool | None = None,
    words_min: int | None = None, words_max: int | None = None,
    letters_min: int | None = None, letters_max: int | None = None,
) -> Filters:
    def nums(s: str | None):
        if not s:
            return None
        return [int(x) for x in re.findall(r"\d+", s)]
    return Filters(sura=nums(sura), juz=nums(juz), hizb=nums(hizb),
                   page_min=page_min, page_max=page_max, revelation=revelation,
                   sajda=sajda, words_min=words_min, words_max=words_max,
                   letters_min=letters_min, letters_max=letters_max)


# ---------------------------------------------------------------------------
# الصفحات
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True, "db": os.path.exists(DB), "db_bytes": os.path.getsize(DB) if os.path.exists(DB) else 0}


# ---------------------------------------------------------------------------
# المعطيات الأساسية
# ---------------------------------------------------------------------------
@app.get("/api/meta", summary="معلومات المحرك والمصادر")
def api_meta():
    e = engine()
    t = dict(e._static["totals"])
    return {"totals": t, "db_bytes": os.path.getsize(DB),
            "sources": {
                "tanzil": "نص تنزيل (الرسم العثماني + الإملائي) — CC BY-ND 3.0 — tanzil.net",
                "corpus": "المجموعة العربية القرآنية v0.4 (صرف) — GPL — corpus.quran.com (كايس ديوكس)",
                "metadata": "بيانات السور والأجزاء والصفحات من تنزيل — CC BY",
            },
            "modes": ["word_exact", "word_prefix", "word_suffix", "word_contains",
                      "anywhere", "letters_across", "phrase"]}


@app.get("/api/suras", summary="قائمة السور مع إحصاءاتها")
def api_suras():
    return {"suras": engine()._static["suras"]}


@app.get("/api/sura/{n}", summary="تفاصيل سورة وآياتها")
def api_sura(n: int, words: bool = False):
    d = engine().sura_page(n, with_words=words)
    if not d:
        raise HTTPException(404, "السورة غير موجودة")
    return d


@app.get("/api/ayah/{sura}/{number}", summary="تفصيل آية: الكلمات، المواضع، الإحصاءات")
def api_ayah(sura: int, number: int):
    d = engine().ayah_page(sura, number)
    if not d:
        raise HTTPException(404, "الآية غير موجودة")
    return d


@app.get("/api/word/{word_id}", summary="تفصيل كلمة: الحروف، الحركات، الموضع، الصرف")
def api_word(word_id: int):
    d = engine().word_detail(word_id)
    if not d:
        raise HTTPException(404, "الكلمة غير موجودة")
    return d


# ---------------------------------------------------------------------------
# البحث
# ---------------------------------------------------------------------------
@app.get("/api/search", summary="البحث الرئيسي")
def api_search(
    q: str = Query(..., description="نص البحث"),
    mode: str = "word_contains",
    tashkeel: bool = Query(False, description="احترام التشكيل المكتوب"),
    ignore_tashkeel: bool = True, unify_alef: bool = True, unify_ya: bool = True,
    unify_ta: bool = True, ignore_hamza: bool = False,
    sura: str | None = None, juz: str | None = None, hizb: str | None = None,
    page_min: int | None = None, page_max: int | None = None,
    revelation: str | None = None, sajda: bool | None = None,
    words_min: int | None = None, words_max: int | None = None,
    letters_min: int | None = None, letters_max: int | None = None,
    proximity: int = 0, limit: int = 100, offset: int = 0,
    with_context: bool = True,
):
    e = engine()
    t0 = time.time()
    opts = opts_from_query(ignore_tashkeel, unify_alef, unify_ya, unify_ta, ignore_hamza)
    f = filters_from_query(sura, juz, hizb, page_min, page_max, revelation, sajda,
                           words_min, words_max, letters_min, letters_max)
    # صيغ مختصرة في نص البحث: ٢:٢٥٥ / 2:255 / جذر:رحم / سورة:يوسف / «عبارة»
    qq, extra = _expand_query(q, e)
    if extra:
        return extra
    res = e.search(qq, mode=mode, opts=opts, filters=f, tashkeel_sensitive=tashkeel,
                   limit=limit, offset=offset, proximity=proximity)
    for m in res.get("matches", []):
        pass
    res["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
    res["filters"] = f.to_dict()
    res["options"] = {"ignore_tashkeel": ignore_tashkeel, "unify_alef": unify_alef,
                      "unify_ya": unify_ya, "unify_ta": unify_ta,
                      "ignore_hamza": ignore_hamza, "tashkeel": tashkeel}
    return res


def _expand_query(q: str, e: QuranEngine):
    """يدعم: ٢:٢٥٥ أو 2:255 مباشرة، جذر:xxx، سورة:xxx، «عبارة»"""
    s = q.strip()
    s_ar = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    m = re.fullmatch(r"(\d{1,3})\s*[:/\.]\s*(\d{1,3})", s_ar)
    if m:
        sura, ayah = int(m.group(1)), int(m.group(2))
        d = e.ayah_page(sura, ayah)
        if not d:
            raise HTTPException(404, "المرجع غير موجود")
        return s, {"query": q, "count": 1, "kind": "ayah_reference",
                   "matches": [_ayah_as_match(d)], "stats": {},
                   "positions": d["stats"]}
    if s.startswith("جذر:") or s.startswith("root:"):
        term = s.split(":", 1)[1].strip()
        rows = e.roots(term, limit=20)
        if len(rows) == 1:
            r = e.root_page(rows[0]["id"])
            return s, {"query": q, "count": r.get("occurrences", 0), "kind": "root",
                       "root": r,
                       "matches": e.search(normalize(rows[0]["arabic"]), mode="word_contains",
                                           limit=100)["matches"]}
        return s, {"query": q, "kind": "root_list", "count": len(rows), "roots": rows,
                   "matches": []}
    if s.startswith("سورة:"):
        term = s.split(":", 1)[1].strip()
        rows = [x for x in e._static["suras"] if term in x["name_ar"] or term == str(x["number"])]
        return s, {"query": q, "kind": "sura_list", "count": len(rows),
                   "suras": rows, "matches": []}
    m = re.fullmatch(r"[«\"'](.+)[»\"']", s)
    if m:
        return s, None
    return s, None


def _ayah_as_match(d: dict) -> dict:
    a = d["ayah"]
    return {"sura": a["sura"], "sura_name": a["name_ar"], "ayah": a["number"],
            "ref": f"{a['sura']}:{a['number']}",
            "ref_ar": f"سورة {a['name_ar']} — الآية {a['number']}",
            "text_uthmani": a["text_uthmani"], "positions": d["stats"],
            "matched_words": [], "words": [{"n": w["number"], "t": w["text_uthmani"],
                                            "l": w["letter_count"], "m": False}
                                           for w in d["words"]]}


@app.get("/api/suggest", summary="اقتراحات إكمال تلقائي")
def api_suggest(q: str, limit: int = 12):
    e = engine()
    if not q.strip():
        return {"items": []}
    n = normalize(q)
    rows = e.q("""SELECT text_norm, count, sura_count FROM word_freq
                  WHERE text_norm LIKE ? ORDER BY count DESC, length(text_norm) LIMIT ?""",
               (n + "%", limit))
    seen, items = set(), []
    for r in rows:
        if r["text_norm"] in seen:
            continue
        seen.add(r["text_norm"])
        sample = e.q("""SELECT text_uthmani FROM word WHERE text_norm=? LIMIT 1""",
                     (r["text_norm"],))
        items.append({"text": r["text_norm"], "display": sample[0]["text_uthmani"] if sample else r["text_norm"],
                      "count": r["count"], "suras": r["sura_count"]})
    return {"items": items}


@app.get("/api/tag", summary="صفحة وسم الكلمة (كل كلمة وسم)")
def api_tag(w: str):
    d = engine().word_tag(w)
    if not d.get("found"):
        raise HTTPException(404, "لا توجد هذه الكلمة")
    return d


@app.get("/api/pos", summary="الأنماط النحوية مع أعدادها")
def api_pos():
    return {"pos": engine()._static["pos_stat"]}


@app.get("/api/pos/search", summary="بحث حسب النمط النحوي")
def api_pos_search(pos: str, limit: int = 100, offset: int = 0, sura: str | None = None,
                   juz: str | None = None):
    f = filters_from_query(sura=sura, juz=juz)
    return engine().pos_search(pos.split(","), filters=f, limit=limit, offset=offset)


@app.get("/api/roots", summary="قائمة الجذور")
def api_roots(q: str = "", limit: int = 100, sort: str = "count"):
    return {"roots": engine().roots(q, limit=limit, sort=sort)}


@app.get("/api/root/{root_id}", summary="صفحة الجذر: الموارد، الصيغ، التوزيع، العلاقات")
def api_root(root_id: int):
    d = engine().root_page(root_id)
    if not d:
        raise HTTPException(404, "الجذر غير موجود")
    return d


@app.get("/api/lemma/{lemma_id}", summary="صفحة المورد (اللمة)")
def api_lemma(lemma_id: int):
    d = engine().lemma_page(lemma_id)
    if not d:
        raise HTTPException(404, "المورد غير موجود")
    return d


@app.get("/api/compare", summary="مقارنة توزيع كلمتين")
def api_compare(w1: str, w2: str):
    return engine().compare_words(w1, w2)


# ---------------------------------------------------------------------------
# الإحصاءات
# ---------------------------------------------------------------------------
@app.get("/api/stats", summary="لوحة الإحصاءات الشاملة")
def api_stats():
    return engine().overview()


@app.get("/api/stats/letters", summary="تكرار الحروف (رسم/مطبَّع)، مع تصفية اختيارية")
def api_stats_letters(kind: str = "norm", sura: int | None = None):
    e = engine()
    if sura:
        rows = e.q("SELECT letter,count FROM sura_letter WHERE kind=? AND sura=? ORDER BY count DESC",
                   (kind, sura))
        total = sum(r["count"] for r in rows) or 1
        return {"kind": kind, "sura": sura,
                "letters": [{"letter": r["letter"], "count": r["count"],
                             "share": round(r["count"] / total * 100, 3)} for r in rows]}
    return {"kind": kind, "letters": e.letter_index()[kind]}


@app.get("/api/stats/ayah-letters/{sura}/{number}", summary="توزيع حروف آية")
def api_ayah_letters(sura: int, number: int):
    e = engine()
    a = e.q("SELECT id FROM ayah WHERE sura=? AND number=?", (sura, number))
    if not a:
        raise HTTPException(404, "الآية غير موجودة")
    return e.letters_for_ayah(a[0]["id"])


@app.get("/api/stats/without-letter", summary="آيات خالية من حرف معيّن")
def api_without_letter(letter: str, limit: int = 50):
    return engine().ayat_without_letter(letter, limit)


@app.get("/api/stats/analysis/{sura}/{number}", summary="تحليل نصّي تفصيلي لآية")
def api_analysis(sura: int, number: int):
    """إحصاءات مفصلة: الحروف، الحركات، الكلمات، الجذور، الأنماط، حساب الجُمّل"""
    e = engine()
    d = e.ayah_page(sura, number)
    if not d:
        raise HTTPException(404, "الآية غير موجودة")
    a = d["ayah"]
    st = text_stats(a["text_uthmani"])
    words = d["words"]
    roots = {}
    pos = {}
    for w in words:
        if w["root_bw"]:
            roots[w["root_bw"]] = roots.get(w["root_bw"], 0) + 1
        pos[w["pos_ar"] or "—"] = pos.get(w["pos_ar"] or "—", 0) + 1
    lens = [w["letter_count"] for w in words]
    return {
        "ref": f"{sura}:{number}", "text": a["text_uthmani"], "text_imlaei": a["text_imlaei"],
        "stats": d["stats"],
        "letters": st.as_dict(),
        "letters_normalized": d["letters"],
        "words": {"count": len(words), "avg_letters": round(sum(lens) / len(lens), 2),
                  "max_letters": max(lens) if lens else 0, "min_letters": min(lens) if lens else 0,
                  "longest": sorted([{"n": w["number"], "t": w["text_uthmani"],
                                      "l": w["letter_count"]} for w in words],
                                    key=lambda x: -x["l"])[:5]},
        "roots": sorted([{"bw": k, "count": v} for k, v in roots.items()],
                        key=lambda x: -x["count"]),
        "pos": sorted([{"pos_ar": k, "count": v} for k, v in pos.items()],
                      key=lambda x: -x["count"]),
        "abjad": {"total": a["abjad_total"], "rule": "حساب الجُمّل المشهور (أ=1، ب=2، ج=3...)"},
        "share": {"letters_of_quran": d["stats"]["letters_share_of_quran"],
                  "words_of_quran": d["stats"]["words_share_of_quran"]},
    }


# ---------------------------------------------------------------------------
# الشبكات والخرائط
# ---------------------------------------------------------------------------
@app.get("/api/graph/roots", summary="شبكة تزامن الجذور")
def api_graph_roots(sura: int | None = None, juz: int | None = None, min_weight: int = 3,
                    limit_nodes: int = 120):
    return engine().root_graph({"sura": sura, "juz": juz}, min_weight=min_weight,
                               limit_nodes=limit_nodes)


@app.get("/api/graph/mindmap", summary="خريطة ذهنية حول جذر")
def api_mindmap(seed: str, depth: int = 2, branch: int = 8, sura: int | None = None):
    return engine().mindmap(seed, depth=depth, branch=branch, scope={"sura": sura})


@app.get("/api/graph/ayah/{sura}/{number}", summary="شبكة علاقات آية واحدة")
def api_graph_ayah(sura: int, number: int):
    return engine().ayah_graph(sura, number)


@app.get("/api/graph/word", summary="شبكة علاقات كلمة (تزامن الكلمات معها)")
def api_graph_word(w: str, limit: int = 25, min_weight: int = 1):
    d = engine().word_graph(w, limit=limit, min_weight=min_weight)
    if not d.get("found"):
        raise HTTPException(404, "الكلمة غير موجودة")
    return d


@app.get("/api/topics", summary="محاور موضوعية مستخرجة من تزامن الجذور")
def api_topics():
    d = engine()
    try:
        rows = d.q("SELECT * FROM topic ORDER BY weight DESC")
    except Exception:
        return {"topics": [], "note": "لم تُبنَ المحاور بعد — شغّل scripts/build_topics.py"}
    out = []
    for t in rows:
        members = d.q("""SELECT r.id,r.arabic,r.count FROM topic_root tr
                         JOIN root r ON r.id=tr.root_id WHERE tr.topic_id=?
                         ORDER BY tr.weight DESC LIMIT 30""", (t["id"],))
        out.append({"id": t["id"], "label": t["label"], "weight": t["weight"],
                    "size": t["size"], "roots": [dict(m) for m in members]})
    return {"topics": out}


@app.get("/api/random", summary="آية عشوائية")
def api_random():
    return engine().random_ayah()


# ---------------------------------------------------------------------------
# الملفات الثابتة
# ---------------------------------------------------------------------------
if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")
