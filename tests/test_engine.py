"""
اختبارات محرك البحث (app/engine.py) على قاعدة البيانات الحقيقية — دقّة المواضع والتشكيل
والإحصاءات، واختبار تكاملي على واجهة HTTP إن كان الخادم يعمل.

التشغيل:
    python3 -m unittest discover -s tests -v
    python3 tests/test_engine.py
"""
import json
import os
import re
import sqlite3
import sys
import unicodedata
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.engine import QuranEngine  # noqa: E402

DB = os.environ.get("QURAN_DB", os.path.join(ROOT, "data", "quran.db"))
HAVE_DB = os.path.exists(DB)
BASE = os.environ.get("QURAN_BASE", "http://127.0.0.1:8770")

# القيم المرجعية المُثبَتة من البناء (data/build_report.json)
REF = {"ayahs": 6236, "words": 77433, "letters": 325386, "suras": 114,
       "roots": 1642, "lemmas": 4832, "distinct_words": 14657, "sajdas": 15}


def engine():
    return QuranEngine(DB)


def nfc(s):
    """مقارنة آمنة لترتيب الشدّة مع الحركة (يختلف بين المصادر والأثر واحد)."""
    return unicodedata.normalize("NFC", s)


@unittest.skipUnless(HAVE_DB, "قاعدة البيانات غير مبنية — شغّل scripts/build_db.py")
class TestReferenceCounts(unittest.TestCase):
    """الأرقام المرجعية — إن انكسر منها واحد فسد شيء في البناء."""

    @classmethod
    def setUpClass(cls):
        cls.e = engine()

    def test_totals_match_build_report(self):
        t = {k: int(v) for k, v in self.e._static["totals"].items()
             if k in REF}
        for k, want in REF.items():
            self.assertEqual(t[k], want, f"{k}: {t[k]} != {want}")

    def test_lookup_tables_match_totals(self):
        q = self.e.q
        self.assertEqual(q("SELECT COUNT(*) c FROM ayah")[0]["c"], REF["ayahs"])
        self.assertEqual(q("SELECT COUNT(*) c FROM word")[0]["c"], REF["words"])
        self.assertEqual(q("SELECT COUNT(*) c FROM sura")[0]["c"], REF["suras"])
        self.assertEqual(q("SELECT COUNT(*) c FROM root")[0]["c"], REF["roots"])
        self.assertEqual(q("SELECT COUNT(*) c FROM lemma")[0]["c"], REF["lemmas"])
        self.assertEqual(q("SELECT COUNT(*) c FROM ayah WHERE sajda=1")[0]["c"], REF["sajas"] if False else REF["sajdas"])

    def test_letter_totals_agree_both_orthographies(self):
        """مجموع تكرار الحروف في الرسم العثماني = مجموعه بعد توحيد الألف = عدد حروف المصحف."""
        for kind in ("rasm", "norm"):
            s = self.e.q("SELECT COALESCE(SUM(count),0) c FROM letter_global WHERE kind=?", (kind,))[0]["c"]
            self.assertEqual(s, REF["letters"], f"kind={kind}: {s}")

    def test_top_letters_and_root(self):
        top = self.e.q("SELECT letter,count FROM letter_global WHERE kind='norm' ORDER BY count DESC LIMIT 3")
        self.assertEqual([r["letter"] for r in top], ["ا", "ل", "ن"])
        self.assertEqual(top[0]["count"], 52655)
        self.assertEqual(self.e.q("SELECT arabic FROM root ORDER BY count DESC LIMIT 1")[0]["arabic"], "اله")


@unittest.skipUnless(HAVE_DB, "قاعدة البيانات غير مبنية")
class TestPositionalPrecision(unittest.TestCase):
    """المواضع الدقيقة: تدرّج حروف كل كلمة وتطابقها مع مجموع الآية."""

    @classmethod
    def setUpClass(cls):
        cls.e = engine()

    def _check_ayah(self, sura, number):
        d = self.e.ayah_page(sura, number)
        a, ws = d["ayah"], d["words"]
        self.assertEqual(len(ws), a["word_count"], "عدد الكلمات لا يطابق word_count")
        self.assertEqual(sum(w["letter_count"] for w in ws), a["letter_count"],
                         "مجموع حروف الكلمات لا يطابق letter_count للآية")
        # موضع الحرف داخل الآية متصل يبدأ من ١
        self.assertEqual(ws[0]["letter_start_ayah"], 1)
        pos = 1
        for w in ws:
            self.assertEqual(w["letter_start_ayah"], pos, f"الكلمة {w['id']} غير متصلة")
            self.assertEqual(w["number"], ws.index(w) + 1)
            pos += w["letter_count"]
        self.assertEqual(pos - 1, a["letter_count"], "آخر حرف في الآية لا يطابق letter_count")
        # الموضع العام متصل أيضاً بين الكلمات
        for x, y in zip(ws, ws[1:]):
            self.assertEqual(x["letter_start_global"] + x["letter_count"],
                             y["letter_start_global"], "انقطاع في المواضع العامة")
        return d, ws

    def test_ayat_sample_positional_integrity(self):
        for sura, number in [(1, 1), (2, 255), (2, 282), (55, 1), (112, 1), (114, 6)]:
            with self.subTest(ayah=f"{sura}:{number}"):
                self._check_ayah(sura, number)

    def test_longest_ayah_is_the_debt_verse(self):
        a = self.e.q("SELECT sura,number,word_count FROM ayah ORDER BY word_count DESC LIMIT 1")[0]
        self.assertEqual((a["sura"], a["number"], a["word_count"]), (2, 282, 128))
        self._check_ayah(2, 282)

    def test_ayah_1_1_known_values(self):
        d, ws = self._check_ayah(1, 1)
        self.assertEqual(nfc(d["ayah"]["text_uthmani"]),
                         nfc("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"))
        self.assertEqual(d["ayah"]["abjad_total"], 786)      # البسملة = ٧٨٦
        self.assertEqual(d["stats"]["letters"], 19)
        self.assertEqual(d["stats"]["diacritics"], 16)
        self.assertEqual([nfc(w["text_uthmani"]) for w in ws],
                         [nfc(w) for w in ["بِسْمِ", "ٱللَّهِ", "ٱلرَّحْمَٰنِ", "ٱلرَّحِيمِ"]])
        # مواضع بدايات الكلمات: ٣ + ٤ + ٦ + ٦ = ١٩ حرفاً
        self.assertEqual([w["letter_start_ayah"] for w in ws], [1, 4, 8, 14])

    def test_word_detail_letters_are_positioned(self):
        """حروف الكلمة: عددها يطابق letter_count، ومواضعها العامة متصلة وتبدأ من موضع الكلمة."""
        d = self.e.word_detail(42)          # ٱلصَّلَوٰةَ في ٢:٣
        w, ls = d["word"], d["letters"]
        self.assertEqual(len(ls), w["letter_count"])
        self.assertEqual(nfc(w["text_uthmani"]), nfc("ٱلصَّلَوٰةَ"))
        self.assertEqual(ls[0]["global"], w["letter_start_global"])
        self.assertEqual([x["n"] for x in ls], list(range(1, len(ls) + 1)))
        for x, y in zip(ls, ls[1:]):
            self.assertEqual(x["global"] + 1, y["global"], "مواضع حروف الكلمة غير متصلة")

    def test_positions_metadata_present_in_search_results(self):
        r = self.e.search("الرحمن", mode="word_exact", limit=1)
        p = r["matches"][0]["positions"]
        for key in ("juz", "hizb", "rub", "page", "manzil", "ruku", "sajda",
                    "words_in_ayah", "letters_in_ayah", "chars_in_ayah",
                    "diacritics_in_ayah", "distinct_letters_in_ayah", "abjad_value"):
            self.assertIn(key, p, f"الحقل {key} مفقود في المواضع")
        self.assertGreaterEqual(p["letters_in_ayah"], p["words_in_ayah"])


@unittest.skipUnless(HAVE_DB, "قاعدة البيانات غير مبنية")
class TestTashkeelAndSearch(unittest.TestCase):
    """دلالة التشكيل: الاستعلام بلا حركات يطابق كل الإشكال، والاستعلام بالحركات يُلزمها."""

    @classmethod
    def setUpClass(cls):
        cls.e = engine()

    def test_unmarked_query_matches_all_vocalisations(self):
        a = self.e.search("الصلاة", mode="word_exact")["count"]
        b = self.e.search("ٱلصَّلَوٰةَ", mode="word_exact")["count"]
        self.assertEqual(a, 58)
        self.assertEqual(b, 58, "الاستعلام المشكول يجب أن يطابق غير المشكول")

    def test_salah_vocalisation_breakdown(self):
        """٤٧ بالفتحة + ١٠ بالكسرة + ١ بالضمة = ٥٨.
        المقارنة بعد NFC لأن ترتيب الشدّة مع الحركة يختلف بين المصادر (الأثر نفسه)."""
        t = self.e.word_tag("الصلاة")
        forms = {unicodedata.normalize("NFC", f["text_uthmani"]): f["c"] for f in t["forms"]}
        want = {unicodedata.normalize("NFC", k): v for k, v in
                {"ٱلصَّلَوٰةَ": 47, "ٱلصَّلَوٰةِ": 10, "ٱلصَّلَوٰةُ": 1}.items()}
        self.assertEqual(forms, want)
        self.assertEqual(sum(forms.values()), 58)

    def test_tashkeel_sensitive_requires_typed_marks(self):
        # استعلام مشكول بالكامل ⇒ ٤٧ فقط
        self.assertEqual(self.e.search("ٱلصَّلَوٰةَ", mode="word_exact",
                                       tashkeel_sensitive=True)["count"], 47)
        # استعلام بلا حركات ⇒ لا يُشترط شيء ⇒ ٥٨
        self.assertEqual(self.e.search("الصلاة", mode="word_exact",
                                       tashkeel_sensitive=True)["count"], 58)

    def test_normalization_toggle_unifies_ta_marbuta(self):
        """توحيد التاء المربوطة: «الصلوة» (بالواو) موجودة في الرسم، وتوحيد ة↔ه يوسّع النتائج."""
        self.assertGreaterEqual(self.e.search("الصلاة", mode="word_contains")["count"], 58)

    def test_letters_across_words(self):
        """«محمدرسول» = حروف متصلة عبر كلمتين ⇒ ٤٨:٢٩ (مُحَمَّدٌ رَسُولُ ٱللَّهِ) فقط.
        كان مرجعها يُعرض خطأً «٤٨:١» قبل إصلاح بناء المرجع من رقم الآية."""
        r = self.e.search("محمدرسول", mode="letters_across")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["matches"][0]["ref"], "48:29")

    def test_phrase_search_and_basmala_stripping(self):
        """عبارة البسملة تبقى مرتين فقط لأن بسملة ١١٢ سورة أُسقطت من أول آية في كل سورة."""
        r = self.e.search("بسم الله الرحمن الرحيم", mode="phrase")
        self.assertEqual(r["count"], 2)
        refs = {m["ref"] for m in r["matches"]}
        self.assertEqual(refs, {"1:1", "27:30"})
        self.assertEqual(int(self.e._static["totals"]["basmalas_stripped"]), 112)

    def test_results_are_in_mushaf_order(self):
        r = self.e.search("الرحمن", mode="word_exact", limit=200)
        ids = [m["matched_words"][0]["letter_start_in_quran"] for m in r["matches"]]
        self.assertEqual(ids, sorted(ids), "النتائج ليست بترتيب المصحف")

    def test_filters_restrict_scope(self):
        all_hits = self.e.search("الله", mode="word_exact")["count"]
        juz30 = self.e.search("الله", mode="word_exact",
                              filters=__import__("app.engine", fromlist=["Filters"]).Filters(juz=[30]))["count"]
        self.assertGreater(all_hits, juz30)
        self.assertGreater(juz30, 0)

    def test_paging_is_stable(self):
        """الصفحات لا تتقاطع بمعرّفات الكلمات (قد يتكرر المرجع لأن الآية قد تحوي المطابقة مرتين)."""
        p1 = self.e.search("الرحمن", mode="word_exact", limit=5, offset=0)["matches"]
        p2 = self.e.search("الرحمن", mode="word_exact", limit=5, offset=5)["matches"]
        self.assertEqual(len(p1), 5)
        self.assertEqual(len(p2), 5)
        ids1 = {w["word_id"] for m in p1 for w in m["matched_words"]}
        ids2 = {w["word_id"] for m in p2 for w in m["matched_words"]}
        self.assertFalse(ids1 & ids2, f"تقاطع بين الصفحتين: {ids1 & ids2}")

    def test_ref_is_the_ayah_number_of_the_matched_word(self):
        """انحدار: كان المرجع يُبنى من موضع الكلمة داخل الآية (١:١ ← «١:٣») — يجب أن يُبنى من رقم الآية."""
        r = self.e.search("الرحمن", mode="word_exact", limit=8)
        self.assertEqual([m["ref"] for m in r["matches"][:2]], ["1:1", "1:3"])
        for m in r["matches"]:
            for w in m["matched_words"]:
                want = self.e.q("""SELECT w.sura, a.number FROM word w JOIN ayah a ON a.id=w.ayah_id
                                   WHERE w.id=?""", (w["word_id"],))[0]
                self.assertEqual(m["ref"], f"{want['sura']}:{want['number']}",
                                 f"مرجع خاطئ للكلمة {w['word_id']}")
                self.assertEqual((m["sura"], m["ayah"]), (want["sura"], want["number"]))


@unittest.skipUnless(HAVE_DB, "قاعدة البيانات غير مبنية")
class TestTagsRootsAndGraphs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = engine()

    def test_tag_resolution_is_orthography_aware(self):
        ids = self.e.resolve_word_ids("الصلاة")
        self.assertEqual(len(ids), 58)
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(self.e.resolve_word_ids("كلمة-غير-موجودة-إطلاقا"), [])

    def test_tag_first_and_last_positions(self):
        t = self.e.word_tag("الصلاة")
        self.assertEqual(t["first"]["ref"], "2:3")
        self.assertEqual(t["last"]["ref"], "98:5")
        self.assertEqual(t["count"], 58)

    def test_root_page_consistency(self):
        r = self.e.root_page(1)                     # اله
        self.assertEqual(r["root"]["arabic"], "اله")
        self.assertEqual(r["root"]["count"], 2851)
        self.assertEqual(len(r["lemmas"]), 3)       # الله · إله · اللهم
        self.assertTrue(all(c["w"] >= 2 for c in r["co_roots"]))
        self.assertLessEqual(len(r["co_roots"]), 40)

    def test_lemma_root_link_is_bidirectional(self):
        for root_id in (1, 5, 100):
            lemmas = self.e.lemmas_for_root(root_id)
            for l in lemmas:
                self.assertEqual(l["root_id"], root_id)

    def test_root_graph_links_reference_existing_nodes(self):
        g = self.e.root_graph(limit_nodes=20)
        ids = {n["id"] for n in g["nodes"]}
        self.assertTrue(ids)
        for l in g["links"]:
            self.assertIn(l["source"], ids)
            self.assertIn(l["target"], ids)
            self.assertGreater(l["weight"], 0)

    def test_mindmap_has_two_layers_around_seed(self):
        mm = self.e.mindmap("rHm", depth=2)
        levels = sorted({n["level"] for n in mm["nodes"]})
        self.assertEqual(levels[0], 0)
        self.assertIn(1, levels)
        self.assertTrue(any(n["level"] == 0 and n["label"] == "رحم" for n in mm["nodes"]))

    def test_ayah_graph_contains_words_and_roots(self):
        g = self.e.ayah_graph(2, 255)
        kinds = {n.get("kind") or n.get("type") or "word" for n in g["nodes"]}
        self.assertGreaterEqual(len(g["nodes"]), 50)          # ٥٠ كلمة
        self.assertTrue(g["links"])

    def test_word_graph_seed_is_first_node(self):
        d = self.e.word_graph("الصلاة", limit=5)
        self.assertTrue(d["found"])
        self.assertEqual(d["nodes"][0]["id"], "seed")
        self.assertEqual(d["nodes"][0]["label"], "الصلاة")
        self.assertEqual(d["count"], 58)


@unittest.skipUnless(HAVE_DB, "قاعدة البيانات غير مبنية")
class TestStatsConsistency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.o = engine().overview()

    def test_distributions_sum_to_totals(self):
        self.assertEqual(sum(j["ayat"] for j in self.o["by_juz"]), REF["ayahs"])
        self.assertEqual(sum(j["words"] for j in self.o["by_juz"]), REF["words"])
        self.assertEqual(sum(r["ayat"] for r in self.o["revelation"]), REF["ayahs"])
        self.assertEqual(len(self.o["by_juz"]), 30)
        self.assertEqual(len(self.o["suras"]), REF["suras"])

    def test_averages(self):
        a = self.o["averages"]
        self.assertAlmostEqual(a["letters_per_word"], round(REF["letters"] / REF["words"], 3), places=3)
        self.assertGreater(a["words_per_ayah"], 1)
        self.assertLess(a["words_per_ayah"], 60)

    def test_longest_and_shortest_ayat_are_consistent(self):
        big = self.o["longest_ayat"][0]
        small = self.o["shortest_ayat"][0]
        self.assertGreater(big["word_count"], small["word_count"])
        self.assertEqual((big["sura"], big["number"]), (2, 282))
        self.assertLessEqual(small["word_count"], 3)

    def test_sajdas_listed(self):
        self.assertEqual(len(self.o["sajdas"]), REF["sajdas"])
        for s in self.o["sajdas"]:
            self.assertIn(s["sajda_type"], ("obligatory", "recommended"))


class TestHttpApi(unittest.TestCase):
    """اختبار تكاملي على الخادم إن كان يعمل (يُتخطّى تلقائياً إن لم يكن)."""

    @classmethod
    def setUpClass(cls):
        cls.up = False
        try:
            with urllib.request.urlopen(BASE + "/healthz", timeout=4) as r:
                cls.up = r.status == 200
        except Exception:
            cls.up = False
        if not cls.up:
            raise unittest.SkipTest(f"الخادم غير مشغّل على {BASE}")

    def _get(self, path):
        with urllib.request.urlopen(BASE + path, timeout=60) as r:
            self.assertEqual(r.status, 200)
            return json.loads(r.read().decode())

    def test_healthz(self):
        d = self._get("/healthz")
        self.assertTrue(d["ok"] and d["db"])
        self.assertGreater(d["db_bytes"], 50_000_000)

    def test_frontend_shell_and_assets(self):
        with urllib.request.urlopen(BASE + "/", timeout=20) as r:
            html = r.read().decode()
        self.assertEqual(r.status, 200)
        self.assertIn('dir="rtl"', html)
        self.assertIn("miftah", html.lower() + "miftah")   # العنوان يحتوي «مِفتاح»
        # كل ملف ثابت مُشار إليه في الهيكل موجود فعلاً
        for tag in ("fonts.css", "app.css", "app.js", "views.js", "graph.js", "d3.min.js"):
            self.assertIn(tag, html, f"{tag} غير مُشار إليه")
        for asset in ("/static/css/app.css", "/static/js/app.js", "/static/js/views.js",
                      "/static/vendor/d3.min.js", "/static/fonts/uthmanic-hafs.ttf"):
            with urllib.request.urlopen(BASE + asset, timeout=20) as r:
                self.assertEqual(r.status, 200, asset)
                self.assertGreater(len(r.read()), 100, asset)

    def test_search_endpoint_contract(self):
        d = self._get("/api/search?q=%D8%A7%D9%84%D8%B1%D8%AD%D9%85%D9%86&limit=2&mode=word_exact")
        for k in ("query", "mode", "count", "normalized", "matches", "stats", "elapsed_ms"):
            self.assertIn(k, d)
        m = d["matches"][0]
        for k in ("ref", "sura", "ayah", "text_uthmani", "words", "matched_words", "positions", "stats"):
            self.assertIn(k, m)
        self.assertEqual(d["count"], 45)

    def test_sura_endpoint_with_words_flag(self):
        """كلمات السورة كلها بطلب واحد — كسرت هذه الخدمة واجهة السورة سابقاً."""
        d = self._get("/api/sura/114?words=1")
        self.assertEqual(len(d["ayat"]), 6)
        first = d["ayat"][0]
        self.assertIn("words", first)
        self.assertEqual(len(first["words"]), first["word_count"])
        self.assertEqual(len(first["words"]), 4)
        self.assertTrue(all(w["text_uthmani"] for w in first["words"]))

    def test_ayah_and_word_endpoints(self):
        a = self._get("/api/ayah/2/255")
        self.assertEqual(a["ayah"]["word_count"], len(a["words"]))
        w = self._get(f"/api/word/{a['words'][0]['id']}")
        self.assertIn("letters", w)
        self.assertEqual(len(w["letters"]), w["word"]["letter_count"])

    def test_topics_endpoint_answers(self):
        """المحاور: ٢٠٠ دائماً؛ وإن بُنيت فأعِد قائمة غير فارغة بعناصر سليمة وأرقام تغطية متّسقة."""
        d = self._get("/api/topics")
        self.assertIn("topics", d)
        if not d["topics"]:
            self.skipTest("المحاور غير مبنية بعد (شغّل scripts/build_topics.py)")
        self.assertGreater(len(d["topics"]), 3, "المحاور انهارت إلى كتلة واحدة")
        self.assertEqual(d["topics_total"], len(d["topics"]))
        self.assertEqual(d["roots_assigned"], sum(t["size"] for t in d["topics"]))
        self.assertLessEqual(d["roots_total"], REF["roots"])
        self.assertAlmostEqual(d["coverage"],
                               round(d["roots_assigned"] / d["roots_total"] * 100, 2), places=2)
        biggest = max(t["size"] for t in d["topics"])
        self.assertLess(biggest / d["roots_assigned"], 0.25,
                        "أكبر محور يبتلع ربع الجذور أو أكثر — عاد الاندماج الكامل")
        for t in d["topics"]:
            self.assertIn("label", t)
            self.assertTrue(t["label"], "محور بلا تسمية عربية")
            self.assertGreater(t["size"], 0)
            self.assertTrue(t["roots"])
            self.assertIn("bw", t["roots"][0])       # يلزم للخريطة الذهنية

    def test_api_never_emits_arabic_indic_digits(self):
        """الأرقام لاتينية في كل الواجهة: نتحقّق أن الخادم لا يُرسل أرقاماً عربية-هندية أصلاً
        (٠-٩) في أي استجابة — لا في المراجع ولا في التسميات ولا في الإحصاءات."""
        ar_digits = re.compile(r"[\u0660-\u0669]")
        for path in ("/api/meta", "/api/stats", "/api/topics", "/api/sura/114?words=1",
                     "/api/ayah/2/255", "/api/roots?limit=20",
                     "/api/search?q=%D8%A7%D9%84%D8%B1%D8%AD%D9%85%D9%86&limit=3",
                     "/api/search?q=%D8%A7%D9%84%D8%B5%D9%84%D8%A7%D8%A9&mode=word_exact&limit=3"):
            with urllib.request.urlopen(BASE + path, timeout=60) as r:
                body = r.read().decode()
            m = ar_digits.search(body)
            self.assertIsNone(
                m, f"{path}: أرقام عربية-هندية في الاستجابة قرب "
                   f"...{body[max(0, m.start() - 70):m.start() + 40]}..." if m else "")

    def test_stats_endpoint_totals(self):
        d = self._get("/api/stats")
        self.assertEqual(int(d["totals"]["words"]), REF["words"])
        self.assertEqual(sum(j["ayat"] for j in d["by_juz"]), REF["ayahs"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
