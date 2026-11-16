#!/usr/bin/env python3
"""
build_db.py — بناء قاعدة بيانات محرك بحث القرآن الكريم
=======================================================
يقرأ المصادر الأصلية (تنزيل + مجموعة ليدز الصرفية) ويبني قاعدة SQLite
تحتوي على: السور، الآيات، الكلمات، المقاطع الصرفية، الجذور، الموارد (لمّات)،
المواضع الدقيقة (حرف/كلمة/آية/سورة/جزء/حزب/ربع/صفحة/منزل/رُكوع)،
وإحصاءات الحروف والحركات على كل المستويات.

المصادر:
  1) Tanzil Quran Text (Uthmani + Simple clean) — CC BY-ND 3.0 — tanzil.net
  2) Quranic Arabic Corpus v0.4 (morphology) — GPL — corpus.quran.com (Kais Dukes)
  3) Tanzil metadata (quran-data.xml) — CC BY — tanzil.net

الاستخدام:
    python3 scripts/build_db.py [--sources data/sources] [--out data/quran.db]
"""
from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import json
import os
import sqlite3
import sys
import time
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.arabic import (  # noqa: E402
    NormOptions, abjad_value, buckwalter_skeleton, buckwalter_to_arabic,
    classify, diacritic_name, letters_only, normalize, search_variants, skeleton,
    text_stats,
)

BASMALA_UTHMANI = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

POS_AR = {
    "N": "اسم", "V": "فعل", "PN": "اسم علم", "PRON": "ضمير", "ADJ": "صفة",
    "DET": "أداة تعريف", "P": "حرف جر", "CONJ": "حرف عطف", "REL": "اسم موصول",
    "DEM": "اسم إشارة", "NEG": "أداة نفي", "INL": "حروف مقطعة", "ACC": "أداة نصب",
    "AMD": "أداة استدراك", "ANS": "أداة جواب", "AVR": "أداة إضراب",
    "CERT": "أداة تقليل الاستثناء", "COND": "أداة شرط", "EMPH": "أداة توكيد",
    "EXH": "أداة تحضيض", "EXL": "أداة استثناء", "EXP": "أداة عرض",
    "FUT": "أداة استقبال", "IMPN": "فعل أمر مبني", "INC": "أداة ابتداء",
    "INT": "أداة استفهام", "INTG": "أداة استفهام", "LOC": "ظرف مكان",
    "PREV": "أداة كفّ", "PRO": "أداة مصدرية", "PRP": "حرف جر",
    "RES": "أداة حصر", "RET": "أداة ردع", "RSLT": "أداة نتيجة",
    "SUB": "أداة مصدرية", "SUP": "أداة استفهام", "SUR": "أداة تصوّر",
    "T": "أداة توكيد", "VOC": "أداة نداء", "CAUS": "أداة سببية",
    "EQ": "أداة تسوية", "CIRC": "حال", "REM": "واو استئنافية",
    "COM": "واو المعية", "IMPV": "لام الأمر", "IMPN": "اسم فعل أمر",
}

FEATURE_AR = {
    "PERF": "ماضٍ", "IMPF": "مضارع", "IMPV": "أمر", "PASS": "مبني للمجهول",
    "ACT": "مبني للمعلوم", "PCPL": "اسم فاعل/مفعول", "VN": "مصدر",
    "NOM": "مرفوع", "ACC": "منصوب", "GEN": "مجرور", "INDEF": "نكرة",
    "M": "مذكر", "F": "مؤنث", "MS": "مفرد مذكر", "FS": "مفرد مؤنث",
    "MD": "مثنى مذكر", "FD": "مثنى مؤنث", "MP": "جمع مذكر", "FP": "جمع مؤنث",
    "P": "جمع", "1S": "متكلم مفرد", "2MS": "مخاطب مذكر", "2FS": "مخاطبة",
    "2MP": "مخاطبون", "2FP": "مخاطبات", "3MS": "غائب مذكر", "3FS": "غائبة",
    "3MP": "غائبون", "3FP": "غائبات", "PREFIX": "سابقة", "STEM": "جذع",
    "SUFFIX": "لاحقة", "SP": "أداة خاصة",
}

SURAH_JEDDAH = {'html': None}


# --------------------------------------------------------------------------
# القراءة
# --------------------------------------------------------------------------

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def read_tanzil(path: str) -> dict[tuple[int, int], str]:
    """قراءة ملف نص تنزيل بصيغة  سورة|آية|نص"""
    out: dict[tuple[int, int], str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or not line[:1].isdigit():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            out[(int(parts[0]), int(parts[1]))] = parts[2]
    return out


def read_metadata(path: str) -> dict:
    # ملف الميتاداتا محلي من مشروع تنزيل، ويُتحقَّق من بصمته (sha256) قبل البناء،
    # فالتحليل الآمن ضد XXE غير لازم هنا؛ لكن لا يُقرأ أي XML من الشبكة في وقت التشغيل.
    root = ET.parse(path).getroot()
    out: dict[str, list] = {}
    for tag in ("suras", "juzs", "hizbs", "manzils", "rukus", "pages", "sajdas"):
        rows = []
        for el in root.find(tag):
            rows.append(dict(el.attrib))
        out[tag] = rows
    return out


def read_corpus(path: str) -> dict[tuple[int, int], dict[int, list[tuple[int, str, str, str]]]]:
    """قراءة مجموعة ليدز الصرفية: (سورة,آية) → {رقم الكلمة: [(رقم المقطع, الشكل, الوسم, السمات)]}"""
    out: dict = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or line.startswith("#") or line.startswith("LOCATION"):
                continue
            f4 = line.split("\t")
            if len(f4) < 4:
                continue
            try:
                s, a, w, seg = (int(x) for x in f4[0].strip("()").split(":"))
            except ValueError:
                continue
            out[(s, a)][w].append((seg, f4[1], f4[2], f4[3]))
    return out


# --------------------------------------------------------------------------
# المحاذاة (بين نص تنزيل ومجموعة ليدز، وبين الرسم العثماني والإملاء)
# --------------------------------------------------------------------------

def char_index_map(src_units: list[str], dst_units: list[str]) -> list[list[int]]:
    """
    محاذاة على مستوى المحارف بين تسلسلين من الوحدات (كلمات).
    ترجع قائمة: لكل وحدة في src قائمة فهارس الوحدات في dst التي تتقاطع معها.
    تستخدم SequenceMatcher على النص المتصل ثم تُسقط تقاطعات المحارف على الوحدات.
    """
    src, dst = "".join(src_units), "".join(dst_units)
    if not src or not dst:
        return [[] for _ in src_units]
    sm = difflib.SequenceMatcher(a=src, b=dst, autojunk=False)

    def bounds(units):
        b, acc = [], 0
        for u in units:
            b.append((acc, acc + len(u)))
            acc += len(u)
        return b

    sb, db = bounds(src_units), bounds(dst_units)

    def idx(B, i):
        lo, hi = 0, len(B) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s0, e0 = B[mid]
            if i < s0:
                hi = mid - 1
            elif i >= e0:
                lo = mid + 1
            else:
                return mid
        return max(0, min(len(B) - 1, lo))

    out: list[set] = [set() for _ in src_units]
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            for k in range(b2 - b1):
                out[idx(sb, a1 + k)].add(idx(db, b1 + k))
        else:
            # كتل غير متطابقة: تُنسب بالتقاطع الموقعي (للتغطية الكاملة)
            for k in range(a1, a2):
                i = idx(sb, k)
                for j in range(b1, b2):
                    out[i].add(idx(db, j))
    return [sorted(s) for s in out]


def join_units(units: list[str], idxs: list[int]) -> str:
    if not idxs:
        return ""
    return " ".join(units[j] for j in idxs if 0 <= j < len(units))


# --------------------------------------------------------------------------
# البناء
# --------------------------------------------------------------------------

def build(sources: str, out_db: str, report_path: str | None = None) -> dict:
    t0 = time.time()
    files = {
        "quran_uthmani": os.path.join(sources, "quran-uthmani.txt"),
        "quran_simple_clean": os.path.join(sources, "quran-simple-clean.txt"),
        "corpus_morphology": os.path.join(sources, "quranic-corpus-morphology-0.4.txt"),
        "tanzil_metadata": os.path.join(sources, "quran-data.xml"),
    }
    for p in files.values():
        if not os.path.exists(p):
            raise SystemExit(f"مصدر مفقود: {p}")

    uthmani = read_tanzil(files["quran_uthmani"])
    imlaei = read_tanzil(files["quran_simple_clean"])
    meta = read_metadata(files["tanzil_metadata"])
    corpus = read_corpus(files["corpus_morphology"])

    if len(uthmani) != 6236 or len(corpus) != 6236:
        raise SystemExit(f"عدد الآيات غير متوقع: uthmani={len(uthmani)} corpus={len(corpus)}")

    # ---- فصل البسملة غير المعدودة عن أوائل السور ----
    basm_u_words = BASMALA_UTHMANI.split()
    nb = len(basm_u_words)
    ayah_uthmani: dict[tuple[int, int], list[str]] = {}
    ayah_imlaei: dict[tuple[int, int], list[str]] = {}
    stripped = 0
    for key, text in uthmani.items():
        s, a = key
        uw = text.split()
        iw = imlaei[key].split()
        if a == 1 and s != 1 and skeleton(uw[0] + uw[1]) == skeleton(basm_u_words[0] + basm_u_words[1]):
            uw, iw = uw[nb:], iw[nb:]
            stripped += 1
        ayah_uthmani[key] = uw
        ayah_imlaei[key] = iw

    # ---- جداول المواضع من ملف الميتاداتا ----
    def build_ranges(pairs: list[tuple[int, int]], n_max: int) -> dict[tuple[int, int], int]:
        """يحوّل قائمة بدايات (سورة,آية) إلى خريطة (سورة,آية) → رقم الموقع"""
        out: dict[tuple[int, int], int] = {}
        keys = sorted(uthmani.keys())
        starts = sorted(pairs, key=lambda x: (x[0], x[1]))
        si = 0
        for k in keys:
            while si + 1 < len(starts) and (starts[si + 1][0], starts[si + 1][1]) <= k:
                si += 1
            out[k] = si + 1
        return out

    juz_map = build_ranges([(int(r["sura"]), int(r["aya"])) for r in meta["juzs"]], 30)
    rub_map = build_ranges([(int(r["sura"]), int(r["aya"])) for r in meta["hizbs"]], 240)
    manzil_map = build_ranges([(int(r["sura"]), int(r["aya"])) for r in meta["manzils"]], 7)
    ruku_map = build_ranges([(int(r["sura"]), int(r["aya"])) for r in meta["rukus"]], 556)
    page_map = build_ranges([(int(r["sura"]), int(r["aya"])) for r in meta["pages"]], 604)
    sajda_map = {(int(r["sura"]), int(r["aya"])): r.get("type", "recommended")
                 for r in meta["sajdas"]}

    # ---- إنشاء قاعدة البيانات ----
    # يُبنى في ملف مؤقت ثم يُنقل نهائياً: يمنع أي حالة جزئية أو WAL قديم عالق.
    tmp_db = out_db + ".tmp"
    for stale in (tmp_db, tmp_db + "-wal", tmp_db + "-shm"):
        if os.path.exists(stale):
            os.remove(stale)
    os.makedirs(os.path.dirname(os.path.abspath(out_db)), exist_ok=True)
    db = sqlite3.connect(tmp_db)
    db.executescript(SCHEMA)

    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "sources": {k: {"file": os.path.basename(v), "sha256": sha256(v),
                              "bytes": os.path.getsize(v)} for k, v in files.items()}}

    # ---------- السور ----------
    suras = {int(r["index"]): r for r in meta["suras"]}
    sura_rows = []
    for n in range(1, 115):
        r = suras[n]
        sura_rows.append((n, r["name"], r["tname"], r["ename"],
                          "مكية" if r["type"] == "Meccan" else "مدنية",
                          int(r["order"]), int(r["ayas"]), int(r["rukus"])))
    db.executemany("INSERT INTO sura(number,name_ar,name_translit,name_en,revelation,"
                   "revelation_order,ayah_count,ruku_count) VALUES (?,?,?,?,?,?,?,?)", sura_rows)

    # ---------- الكلمات والآيات والحروف ----------
    word_rows, ayah_rows, word_norm_rows = [], [], []
    ayah_letter_rows, ayah_diacritic_rows = [], []
    root_ayah_rows = []
    letter_global = collections.Counter()
    letter_norm_global = collections.Counter()
    sura_letter = collections.Counter()
    sura_letter_norm = collections.Counter()
    sura_diacritic = collections.Counter()
    sura_letter_sets: dict[int, set] = collections.defaultdict(set)

    root_bw_count = collections.Counter()
    lemma_bw_count = collections.Counter()
    lemma_surface = collections.defaultdict(collections.Counter)
    lemma_root: dict[str, str] = {}
    lemma_pos: dict[str, str] = {}
    root_sura = collections.Counter()

    wid = 0                    # فهرس الكلمات العالمي
    lid = 0                    # فهرس الحروف العالمي
    aid = 0                    # فهرس الآيات العالمي
    sura_word_count = collections.Counter()
    sura_word_start: dict[int, int] = {}
    sura_letter_start: dict[int, int] = {}
    sura_letter_count = collections.Counter()
    alignment_report = {"ayahs_need_alignment": 0, "unmatched_words": 0,
                        "corpus_word_lists_mismatch": 0, "imlaei_align_fail": 0}
    merged_pairs = []

    for (s, a) in sorted(uthmani.keys()):
        aid += 1
        uw = ayah_uthmani[(s, a)]
        iw = ayah_imlaei[(s, a)]
        text_u = " ".join(uw)
        text_i = " ".join(iw)
        norm_i = normalize(text_i)
        st = text_stats(text_u)

        cwords = corpus.get((s, a), {})
        cw_keys = sorted(cwords.keys())
        cw_texts_bw = ["".join(seg[1] for seg in cwords[w]) for w in cw_keys]
        cw_skel = [buckwalter_skeleton(t) for t in cw_texts_bw]
        uw_skel = [skeleton(w) for w in uw]

        if len(cw_keys) != len(uw) or uw_skel != cw_skel:
            alignment_report["ayahs_need_alignment"] += 1
        # محاذاة: uthmani word index → corpus word indexes
        c2u = char_index_map(cw_skel, uw_skel)       # corpus → uthmani
        u2c = char_index_map(uw_skel, cw_skel)       # uthmani → corpus
        for i, cc in enumerate(c2u):
            if len(cc) > 1:
                merged_pairs.append({"sura": s, "ayah": a, "corpus_word": i + 1,
                                     "uthmani_words": [c + 1 for c in cc]})
        # محاذاة الكلمات العثمانية مع كلمات الإملاء — تُجرى على النص المطبَّع
        # (المحاذاة على الرسم الخام تفشل لأن الرسمين مختلفان إملائياً).
        uw_norm = [normalize(w, NormOptions(khanjariyya_as_alef=True)) for w in uw]
        iw_norm = [normalize(w, NormOptions(khanjariyya_as_alef=True)) for w in iw]
        u2i = char_index_map(uw_norm, iw_norm) if len(iw) != len(uw) else None

        ayah_word_ids = []
        ayah_letters = collections.Counter()
        ayah_diacritics = collections.Counter()
        ayah_letters_norm = collections.Counter()       # بعد توحيد الألف والهمزات
        letter_cursor_ayah = 0        # عدد حروف الآية المتراكمة
        char_pos_ayah = 0             # موضع المحرف داخل الآية (للإبراز الدقيق)
        for ch in letters_only(normalize(text_u)):
            ayah_letters_norm[ch] += 1
            sura_letter_norm[(s, ch)] += 1
            letter_norm_global[ch] += 1

        for wi, wtext in enumerate(uw, start=1):
            wid += 1
            wst = text_stats(wtext)
            # المواضع الدقيقة: الحروف والكلمات والفواصل
            lt_start_ayah = letter_cursor_ayah + 1
            lt_start_global = lid + 1
            char_start = char_pos_ayah
            char_end = char_pos_ayah + len(wtext)
            char_pos_ayah = char_end + 1                      # +1 للفراغ
            letter_cursor_ayah += wst.letters
            lid += wst.letters

            # الإملاء المقابل: المحاذاة إن وُجدت، وإلا الشكل المشتق بالتوحيد
            if u2i is not None:
                txt_iml = join_units(iw, u2i[wi - 1])
            else:
                txt_iml = iw[wi - 1] if wi - 1 < len(iw) else ""
            if not txt_iml:
                txt_iml = normalize(wtext, NormOptions(khanjariyya_as_alef=True))
                alignment_report["imlaei_fallback"] = alignment_report.get("imlaei_fallback", 0) + 1
            # الصرف: كل مقاطع مجموعة ليدز التي تنتمي لهذه الكلمة
            # ملاحظة مهمة: عمود TAG يحمل النوع النحوي (N/V/P…)، أما STEM/PREFIX/SUFFIX
            # فتقع في عمود FEATURES. الجذور والموارد تُؤخذ من الجذع (STEM) أولاً.
            segs = []
            for ci in u2c[wi - 1]:
                for (seg_no, form, tag, feats) in sorted(cwords.get(cw_keys[ci], [])):
                    d = dict(x.split(":", 1) if ":" in x else (x, "") for x in feats.split("|"))
                    role = ("STEM" if "STEM" in d else
                            "PREFIX" if "PREFIX" in d else
                            "SUFFIX" if "SUFFIX" in d else "")
                    segs.append({"n": seg_no, "form": form, "tag": tag,
                                 "role": role, "features": feats,
                                 "bw": form, "pos": d.get("POS"),
                                 "root": d.get("ROOT"), "lemma": d.get("LEM")})
            stems = [x for x in segs if x["role"] == "STEM"]
            src = (stems or [x for x in segs if x["pos"]] or segs)
            root_bw = next((x["root"] for x in src if x["root"]), None)
            lemma_bw = next((x["lemma"] for x in src if x["lemma"]), None)
            pos = next((x["pos"] for x in src if x["pos"]), None) or (segs[0]["tag"] if segs else None)
            if lemma_bw is None:
                lemma_bw = next((x["lemma"] for x in segs if x["lemma"]), None)
            if root_bw is None:
                root_bw = next((x["root"] for x in segs if x["root"]), None)
            # حالات الاندماج الإملائي: كلمة مجموعة ليدز واحدة تغطي أكثر من كلمة عثمانية
            # (مثل «بَعْدَ مَا» تُكتب «بَعْدَمَا») — تُنسب الصرفيات للكلمة الأولى فقط.
            if any(len(c2u[ci]) > 1 and c2u[ci][0] != wi - 1 for ci in u2c[wi - 1]):
                segs = [{"n": 0, "form": "", "tag": "—", "role": "",
                         "features": "MERGED_WITH_PREVIOUS",
                         "note": "مدموجة إملائياً مع الكلمة السابقة في المصحف"}]
                root_bw = lemma_bw = None
                pos = "—"

            root_id = lemma_id = None
            if root_bw:
                root_bw_count[root_bw] += 1
                root_sura[(root_bw, s)] += 1
            if lemma_bw:
                lemma_bw_count[lemma_bw] += 1
                lemma_surface[lemma_bw][wtext] += 1
                if root_bw:
                    lemma_root[lemma_bw] = root_bw
                if pos:
                    lemma_pos[lemma_bw] = pos

            word_rows.append((
                wid, s, aid, wi, wtext, txt_iml, letters_only(wtext), normalize(wtext),
                wst.letters, wst.diacritics, wst.quran_marks, len(wtext), abjad_value(wtext),
                wst.distinct_letters.__len__(),
                lt_start_ayah, lt_start_global, char_start, char_end,
                root_bw, lemma_bw, pos, None,
                json.dumps(segs, ensure_ascii=False),
            ))
            for kind, v in (("u1", search_variants(wtext, NormOptions(khanjariyya_as_alef=False))),
                            ("u2", search_variants(wtext, NormOptions(khanjariyya_as_alef=True))),
                            ("i", search_variants(normalize(txt_iml)) if txt_iml else [])):
                for t in v:
                    word_norm_rows.append((wid, kind, t))
            ayah_word_ids.append(wid)
            sura_word_count[s] += 1
            sura_letter_count[s] += wst.letters
            for ch, c in wst.by_letter.items():
                letter_global[ch] += c
                sura_letter[(s, ch)] += c
                ayah_letters[ch] += c
                sura_letter_sets[s].add(ch)
            for nm, c in wst.by_diacritic.items():
                ayah_diacritics[nm] += c
                sura_diacritic[(s, nm)] += c
            if root_bw:
                root_ayah_rows.append((root_bw, aid, s))

        total_letters = sum(ayah_letters.values())
        ayah_rows.append((
            aid, s, a, text_u, text_i, letters_only(text_u), norm_i,
            len(uw), total_letters, len(text_u), sum(ayah_diacritics.values()),
            len(ayah_letters), abjad_value(text_u),
            juz_map[(s, a)], (rub_map[(s, a)] - 1) // 4 + 1, rub_map[(s, a)],
            manzil_map[(s, a)], ruku_map[(s, a)], page_map[(s, a)],
            1 if (s, a) in sajda_map else 0, sajda_map.get((s, a)),
            ayah_word_ids[0], ayah_word_ids[-1],
            lid - total_letters + 1, lid,
        ))
        for ch, c in ayah_letters.items():
            ayah_letter_rows.append(("rasm", aid, normalize(ch, NormOptions(strip_hamza=False)), c))
        for ch, c in ayah_letters_norm.items():
            ayah_letter_rows.append(("norm", aid, ch, c))
        for nm, c in ayah_diacritics.items():
            ayah_diacritic_rows.append((aid, nm, c))

    db.executemany(
        "INSERT INTO ayah(id,sura,number,text_uthmani,text_imlaei,text_bare,text_norm,"
        "word_count,letter_count,char_count,diacritic_count,distinct_letters,abjad_total,"
        "juz,hizb,rub,manzil,ruku,page,sajda,sajda_type,word_start,word_end,"
        "letter_start,letter_end) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ayah_rows)
    db.executemany(
        "INSERT INTO word(id,sura,ayah_id,number,text_uthmani,text_imlaei,text_bare,text_norm,"
        "letter_count,diacritic_count,quran_mark_count,char_count,abjad,distinct_letters,"
        "letter_start_ayah,letter_start_global,char_start_ayah,char_end_ayah,"
        "root_bw,lemma_bw,pos,pos_ar,segments) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        word_rows)
    db.executemany("INSERT INTO word_norm(word_id,kind,text) VALUES (?,?,?)", word_norm_rows)
    db.executemany("INSERT INTO ayah_letter(kind,ayah_id,letter,count) VALUES (?,?,?,?)", ayah_letter_rows)
    db.executemany("INSERT INTO ayah_diacritic(ayah_id,name,count) VALUES (?,?,?)", ayah_diacritic_rows)

    # ---------- الجذور والموارد ----------
    root_id_map, lemma_id_map = {}, {}
    # أشكال كل جذور: تُحسب بمرور واحد (تجنّب O(الجذور × الكلمات))
    root_forms: dict[str, set] = collections.defaultdict(set)
    for w in word_rows:
        if w[18]:
            root_forms[w[18]].add(w[4])
    root_rows = []
    for i, (bw, cnt) in enumerate(sorted(root_bw_count.items(), key=lambda x: (-x[1], x[0])), start=1):
        root_id_map[bw] = i
        root_rows.append((i, bw, buckwalter_to_arabic(bw, keep_marks=False), cnt,
                          len(root_forms[bw])))
    db.executemany("INSERT INTO root(id,bw,arabic,count,form_count) VALUES (?,?,?,?,?)", root_rows)

    lemma_rows = []
    for i, (bw, cnt) in enumerate(sorted(lemma_bw_count.items(), key=lambda x: (-x[1], x[0])), start=1):
        lemma_id_map[bw] = i
        surf = lemma_surface[bw]
        common = surf.most_common(1)[0][0] if surf else ""
        rbw = lemma_root.get(bw)
        lemma_rows.append((i, bw, buckwalter_to_arabic(bw, keep_marks=True), common, cnt,
                           root_id_map.get(rbw) if rbw else None,
                           lemma_pos.get(bw), len(surf)))
    db.executemany("INSERT INTO lemma(id,bw,arabic,surface_common,count,root_id,pos,form_count)"
                   " VALUES (?,?,?,?,?,?,?,?)", lemma_rows)

    db.executemany("UPDATE word SET root_id=?, lemma_id=?, pos_ar=? WHERE id=?",
                   [(root_id_map.get(w[18]), lemma_id_map.get(w[19]),
                     POS_AR.get(w[20], w[20]), w[0]) for w in word_rows])

    root_ayah_rows = [(root_id_map[r], a, s, 1) for (r, a, s) in root_ayah_rows if r in root_id_map]
    db.executemany("INSERT INTO root_ayah(root_id,ayah_id,sura,count) VALUES (?,?,?,?)", root_ayah_rows)
    db.executemany("INSERT INTO root_sura(root_id,sura,count) VALUES (?,?,?)",
                   [(root_id_map[r], s, c) for (r, s), c in root_sura.items() if r in root_id_map])

    # ---------- الإحصاءات ----------
    db.executemany("INSERT INTO sura_letter(kind,sura,letter,count) VALUES (?,?,?,?)",
                   [("rasm", s, ch, c) for (s, ch), c in sura_letter.items()] +
                   [("norm", s, ch, c) for (s, ch), c in sura_letter_norm.items()])
    db.executemany("INSERT INTO sura_diacritic(sura,name,count) VALUES (?,?,?)",
                   [(s, nm, c) for (s, nm), c in sura_diacritic.items()])
    for kind, counter in (("rasm", letter_global), ("norm", letter_norm_global)):
        for rank, (ch, c) in enumerate(counter.most_common(), start=1):
            db.execute("INSERT INTO letter_global(kind,letter,count,rank) VALUES (?,?,?,?)",
                       (kind, ch, c, rank))

    # تحديث إحصاءات السور
    for n in range(1, 115):
        db.execute(
            "UPDATE sura SET word_count=?, letter_count=?, distinct_letters=?, "
            "char_count=COALESCE((SELECT SUM(char_count) FROM ayah WHERE sura=?),0), "
            "diacritic_count=COALESCE((SELECT SUM(diacritic_count) FROM ayah WHERE sura=?),0), "
            "abjad_total=COALESCE((SELECT SUM(abjad_total) FROM ayah WHERE sura=?),0), "
            "juz_start=(SELECT MIN(juz) FROM ayah WHERE sura=?), "
            "juz_end=(SELECT MAX(juz) FROM ayah WHERE sura=?), "
            "page_start=(SELECT MIN(page) FROM ayah WHERE sura=?), "
            "page_end=(SELECT MAX(page) FROM ayah WHERE sura=?) WHERE number=?",
            (sura_word_count[n], sura_letter_count[n], len(sura_letter_sets[n]),
             n, n, n, n, n, n, n, n))

    # ---------- تكرار الكلمات (الوسوم) ----------
    db.execute("""
        INSERT INTO word_freq(text_norm, count, sura_count, first_ayah, root_id, lemma_id, pos)
        SELECT text_norm, COUNT(*), COUNT(DISTINCT sura), MIN(ayah_id),
               (SELECT root_id FROM word w2 WHERE w2.text_norm=w.text_norm AND w2.root_id IS NOT NULL LIMIT 1),
               (SELECT lemma_id FROM word w2 WHERE w2.text_norm=w.text_norm AND w2.lemma_id IS NOT NULL LIMIT 1),
               (SELECT pos FROM word w2 WHERE w2.text_norm=w.text_norm AND w2.pos IS NOT NULL LIMIT 1)
        FROM word w WHERE text_norm <> '' GROUP BY text_norm
    """)
    # ---------- تكرار الجذور/الموارد/الأنماط ----------
    for bw, rid in root_id_map.items():
        db.execute("UPDATE root SET sura_count=(SELECT COUNT(DISTINCT sura) FROM word WHERE root_id=?) WHERE id=?", (rid, rid))
        db.execute("UPDATE root SET lemma_count=(SELECT COUNT(*) FROM lemma WHERE root_id=?) WHERE id=?", (rid, rid))
    db.execute("""INSERT INTO pos_stat(pos, pos_ar, count, word_count, sura_count)
                  SELECT COALESCE(pos,'—'), COALESCE(MAX(pos_ar),'—'), COUNT(*),
                         COUNT(DISTINCT text_norm), COUNT(DISTINCT sura)
                  FROM word GROUP BY pos""")

    # ---------- الفهرس الكامل للبحث في الآيات ----------
    db.executemany("INSERT INTO ayah_norm(ayah_id,kind,text) VALUES (?,?,?)",
                   [(a[0], "imlaei", a[6]) for a in ayah_rows] +
                   [(a[0], "uthmani", normalize(a[3])) for a in ayah_rows] +
                   [(a[0], "bare", normalize(a[5])) for a in ayah_rows])
    db.executemany("INSERT INTO sura_norm(sura,text) VALUES (?,?)",
                   [(n, normalize(" ".join(a[3] for a in ayah_rows if a[1] == n))) for n in range(1, 115)])

    # ---------- ميتاداتا البناء ----------
    total_diacritics = db.execute("SELECT SUM(diacritic_count) FROM ayah").fetchone()[0] or 0
    totals = {
        "ayahs": len(ayah_rows), "words": len(word_rows), "letters": sum(letter_global.values()),
        "diacritics": total_diacritics,
        "suras": 114, "roots": len(root_rows), "lemmas": len(lemma_rows),
        "distinct_words": db.execute("SELECT COUNT(*) FROM word_freq").fetchone()[0],
        "distinct_letters": len(letter_global), "chars": sum(a[9] for a in ayah_rows),
        "basmalas_stripped": stripped, "sajdas": len(sajda_map),
        "morph_segments": sum(len(json.loads(w[22])) for w in word_rows),
        "words_with_root": sum(1 for w in word_rows if w[18]),
        "words_without_root": sum(1 for w in word_rows if not w[18]),
    }
    for k, v in totals.items():
        db.execute("INSERT INTO meta(key,value) VALUES (?,?)", (k, str(v)))
    db.executemany("INSERT INTO meta(key,value) VALUES (?,?)",
                   [(f"source_{k}_sha256", v["sha256"]) for k, v in report["sources"].items()])

    db.commit()
    db.executescript("ANALYZE;")
    db.execute("PRAGMA journal_mode=DELETE;")
    db.commit()
    db.close()
    os.replace(tmp_db, out_db)
    for stale in (tmp_db + "-wal", tmp_db + "-shm"):
        if os.path.exists(stale):
            os.remove(stale)

    report.update(totals)
    report["alignment"] = alignment_report
    report["corpus_word_merges"] = merged_pairs
    report["build_seconds"] = round(time.time() - t0, 2)
    report["db_bytes"] = os.path.getsize(out_db)
    report["db_sha256"] = sha256(out_db)
    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    return report


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=OFF;
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE sura(
  number INTEGER PRIMARY KEY, name_ar TEXT, name_translit TEXT, name_en TEXT,
  revelation TEXT, revelation_order INTEGER, ayah_count INTEGER, ruku_count INTEGER,
  word_count INTEGER DEFAULT 0, letter_count INTEGER DEFAULT 0, char_count INTEGER DEFAULT 0,
  diacritic_count INTEGER DEFAULT 0, distinct_letters INTEGER DEFAULT 0,
  abjad_total INTEGER DEFAULT 0, juz_start INTEGER, juz_end INTEGER,
  page_start INTEGER, page_end INTEGER);
CREATE TABLE ayah(
  id INTEGER PRIMARY KEY, sura INTEGER, number INTEGER,
  text_uthmani TEXT, text_imlaei TEXT, text_bare TEXT, text_norm TEXT,
  word_count INTEGER, letter_count INTEGER, char_count INTEGER, diacritic_count INTEGER,
  distinct_letters INTEGER, abjad_total INTEGER,
  juz INTEGER, hizb INTEGER, rub INTEGER, manzil INTEGER, ruku INTEGER, page INTEGER,
  sajda INTEGER DEFAULT 0, sajda_type TEXT,
  word_start INTEGER, word_end INTEGER, letter_start INTEGER, letter_end INTEGER,
  UNIQUE(sura,number));
CREATE TABLE word(
  id INTEGER PRIMARY KEY, sura INTEGER, ayah_id INTEGER, number INTEGER,
  text_uthmani TEXT, text_imlaei TEXT, text_bare TEXT, text_norm TEXT,
  letter_count INTEGER, diacritic_count INTEGER, quran_mark_count INTEGER,
  char_count INTEGER, abjad INTEGER, distinct_letters INTEGER,
  letter_start_ayah INTEGER, letter_start_global INTEGER,
  char_start_ayah INTEGER, char_end_ayah INTEGER,
  root_bw TEXT, lemma_bw TEXT, pos TEXT, pos_ar TEXT, segments TEXT,
  root_id INTEGER, lemma_id INTEGER);
CREATE TABLE word_norm(word_id INTEGER, kind TEXT, text TEXT);
CREATE TABLE ayah_norm(ayah_id INTEGER, kind TEXT, text TEXT);
CREATE TABLE sura_norm(sura INTEGER, text TEXT);
CREATE TABLE root(id INTEGER PRIMARY KEY, bw TEXT, arabic TEXT, count INTEGER,
  form_count INTEGER, sura_count INTEGER DEFAULT 0, lemma_count INTEGER DEFAULT 0);
CREATE TABLE lemma(id INTEGER PRIMARY KEY, bw TEXT, arabic TEXT, surface_common TEXT,
  count INTEGER, root_id INTEGER, pos TEXT, form_count INTEGER);
CREATE TABLE root_ayah(root_id INTEGER, ayah_id INTEGER, sura INTEGER, count INTEGER);
CREATE TABLE root_sura(root_id INTEGER, sura INTEGER, count INTEGER);
CREATE TABLE word_freq(text_norm TEXT PRIMARY KEY, count INTEGER, sura_count INTEGER,
  first_ayah INTEGER, root_id INTEGER, lemma_id INTEGER, pos TEXT);
CREATE TABLE letter_global(kind TEXT, letter TEXT, count INTEGER, rank INTEGER,
  PRIMARY KEY(kind,letter));
CREATE TABLE sura_letter(kind TEXT, sura INTEGER, letter TEXT, count INTEGER);
CREATE TABLE sura_diacritic(sura INTEGER, name TEXT, count INTEGER);
CREATE TABLE ayah_letter(kind TEXT, ayah_id INTEGER, letter TEXT, count INTEGER);
CREATE TABLE ayah_diacritic(ayah_id INTEGER, name TEXT, count INTEGER);
CREATE TABLE pos_stat(pos TEXT PRIMARY KEY, pos_ar TEXT, count INTEGER,
  word_count INTEGER, sura_count INTEGER);
CREATE INDEX idx_word_sura ON word(sura);
CREATE INDEX idx_word_ayah ON word(ayah_id);
CREATE INDEX idx_word_norm ON word(text_norm);
CREATE INDEX idx_word_root ON word(root_id);
CREATE INDEX idx_word_lemma ON word(lemma_id);
CREATE INDEX idx_word_pos ON word(pos);
CREATE INDEX idx_wnorm_text ON word_norm(text);
CREATE INDEX idx_anorm_text ON ayah_norm(text);
CREATE INDEX idx_root_ayah ON root_ayah(ayah_id);
CREATE INDEX idx_root_ayah_r ON root_ayah(root_id);
CREATE INDEX idx_root_sura ON root_sura(root_id);
CREATE INDEX idx_ayah_sura ON ayah(sura);
CREATE INDEX idx_ayah_juz ON ayah(juz);
CREATE INDEX idx_ayah_page ON ayah(page);
CREATE INDEX idx_ayah_hizb ON ayah(hizb);
CREATE INDEX idx_ayah_letter ON ayah_letter(kind,letter);
CREATE INDEX idx_alah_letter ON ayah_letter(kind,letter,ayah_id);
CREATE INDEX idx_sura_letter ON sura_letter(kind,letter);
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="بناء قاعدة بيانات محرك بحث القرآن")
    ap.add_argument("--sources", default="data/sources")
    ap.add_argument("--out", default="data/quran.db")
    ap.add_argument("--report", default="data/build_report.json")
    args = ap.parse_args()
    rep = build(args.sources, args.out, args.report)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
