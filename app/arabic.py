"""
arabic.py — طبقة معالجة النص العربي للقرآن الكريم
=================================================
مسؤولة عن: التطبيع (تجاهل التشكيل) ، توحيد الأشكال ، فك ترميز بكوولتر ،
تصنيف الحروف والحركات وعلامات الوقف ، والمطابقة الحساسة للتشكيل.

كل الدوال نقية (pure) ويعاد استخدامها في بناء الفهرس وفي وقت البحث
لضمان أن تطبيع الاستعلام مطابق تماماً لتطبيع النص المفهرس.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# 1) مجموعات المحارف
# --------------------------------------------------------------------------

TATWEEL = "\u0640"                     # ـ  كشيدة
SMALL_WAW = "\u06e5"                   # ۥ
SMALL_YEH = "\u06e6"                   # ۦ
SMALL_HIGH_MEEM = "\u06e2"             # ۢ (iqlab)

# علامات قرآنية / علامات وقف (لا تُعدّ حروفاً ولا حركات)
QURAN_MARKS = (
    set(range(0x0610, 0x061B))         # علامات صوتية
    | {0x06DD, 0x06DE}                 # ۝ end of ayah, rub el hizb
    | set(range(0x06D6, 0x06ED))       # علامات الوقف الصغيرة
    | set(range(0x08F0, 0x08F4))
    | set(range(0x08E3, 0x0900))       # علامات عربية موسّعة
)

# الحركات والتشكيل (Mn/Me عدا ما سبق)
DIACRITICS = {
    0x064B: "tanwin_fath", 0x064C: "tanwin_damm", 0x064D: "tanwin_kasr",
    0x064E: "fatha", 0x064F: "damma", 0x0650: "kasra", 0x0651: "shadda",
    0x0652: "sukun", 0x0653: "madda", 0x0654: "hamza_above",
    0x0655: "hamza_below", 0x0656: "subscript_alef", 0x0657: "inverted_damma",
    0x0658: "mark_above", 0x0670: "alef_khanjariyya",
    0x06DF: "small_high_rounded_zero", 0x06E0: "small_high_upright_rect",
    0x06E1: "small_high_dotless_head", 0x06E3: "small_low_meem",
    0x06E4: "small_high_meem", 0x06E7: "small_high_yeh", 0x06E8: "small_high_noon",
    0x06EA: "empty_centre_low_stop", 0x06EB: "empty_centre_high_stop",
    0x06EC: "rounded_high_stop", 0x06ED: "small_low_meem_isolated",
}

# الأشكال البديلة للحروف
ALEF_FORMS = "\u0622\u0623\u0625\u0671"   # آ أ إ ٱ
HARAKAT = {"fatha", "damma", "kasra", "tanwin_fath", "tanwin_damm", "tanwin_kasr"}

ARABIC_LETTERS = set(
    "ابتثجحخدذرزسشصضطظعغفقكلمنهويء" + "أإآٱؤئىة" + "\u0670"
)


def is_arabic_letter(ch: str) -> bool:
    """هل المحرف حرف عربي (لا حركة ولا علامة)؟"""
    cp = ord(ch)
    if cp in QURAN_MARKS or ch in (TATWEEL, SMALL_WAW, SMALL_YEH):
        return False
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Me", "Cf", "Cc"):
        return False
    if cp == 0x0670:          # ألف خنجرية (حركة في الحقيقة)
        return False
    return unicodedata.name(ch, "").startswith("ARABIC") or ch in ARABIC_LETTERS


def classify(ch: str) -> str:
    """تصنيف محرف: letter | diacritic | quran_mark | tatweel | small_letter | other"""
    cp = ord(ch)
    if ch == TATWEEL:
        return "tatweel"
    if ch in (SMALL_WAW, SMALL_YEH):
        return "small_letter"
    if cp in QURAN_MARKS:
        return "quran_mark"
    if cp in DIACRITICS or unicodedata.category(ch) in ("Mn", "Me"):
        return "diacritic"
    if is_arabic_letter(ch):
        return "letter"
    return "other"


def diacritic_name(ch: str) -> str:
    return DIACRITICS.get(ord(ch), "diacritic:" + hex(ord(ch)))


# --------------------------------------------------------------------------
# 2) التطبيع
# --------------------------------------------------------------------------

@dataclass
class NormOptions:
    """خيارات التطبيع — تُطبَّق بنفس الطريقة على النص وعلى الاستعلام."""
    strip_tashkeel: bool = True       # تجاهل التشكيل
    unify_alef: bool = True           # توحيد الألف: آ أ إ ٱ ← ا
    unify_ya: bool = True             # ى ← ي
    unify_ta_marbuta: bool = True     # ة ← ه
    strip_hamza: bool = False         # ؤ ← و ، ئ ← ي ، ء ← حذف
    khanjariyya_as_alef: bool = False # ٰ ← ا  (مقابل حذفها)
    keep_shadda: bool = False
    strip_quran_marks: bool = True    # حذف علامات الوقف والأرقام
    drop_small_letters: bool = True


DEFAULT = NormOptions()


def _strip_marks(text: str, opts: NormOptions) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        kind = classify(ch)
        if kind == "tatweel":
            continue
        if kind == "quran_mark":
            if opts.strip_quran_marks:
                continue
            out.append(ch); continue
        if kind == "small_letter":
            if opts.drop_small_letters:
                continue
            out.append(ch); continue
        if kind == "diacritic":
            if cp == 0x0670:                      # ألف خنجرية
                if opts.strip_tashkeel or opts.khanjariyya_as_alef:
                    if opts.khanjariyya_as_alef:
                        out.append("\u0627")
                else:
                    out.append(ch)
                continue
            if opts.strip_tashkeel:
                if opts.keep_shadda and cp == 0x0651:
                    out.append(ch)
                continue
            out.append(ch); continue
        out.append(ch)
    return "".join(out)


def normalize(text: str, opts: NormOptions | None = None) -> str:
    """تطبيع نص عربي للبحث: يزيل التشكيل ويوحّد الأشكال ويقلّص المسافات."""
    opts = opts or DEFAULT
    if text is None:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _strip_marks(text, opts)
    if opts.unify_alef:
        table = {ord(c): "\u0627" for c in ALEF_FORMS}
        text = text.translate(table)
    if opts.unify_ya:
        text = text.replace("\u0649", "\u064a")        # ى ← ي
    if opts.unify_ta_marbuta:
        text = text.replace("\u0629", "\u0647")        # ة ← ه
    if opts.strip_hamza:
        text = text.replace("\u0624", "\u0648").replace("\u0626", "\u064a")
        text = text.replace("\u0621", "")
    # إزالة التشكيل المتبقي بعد التوحيد (قد ينتج عن التبديلات)
    if opts.strip_tashkeel:
        text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("M"))
    text = re.sub(r"[\u200c\u200d\u200e\u200f\ufeff]", "", text)   # محارف تحكم
    text = re.sub(r"[^\S\n]+", " ", text)
    return text.strip()


def skeleton(text: str) -> str:
    """الهيكل الصرفي: حروف فقط بلا تشكيل ولا همزات ولا علامات — للمطابقة الصلبة."""
    return normalize(text, NormOptions(strip_hamza=True, khanjariyya_as_alef=False))


def search_variants(text: str, opts: NormOptions | None = None) -> list[str]:
    """الأشكال البديلة للنص أو للاستعلام (تُفهرس كلها) لضمان عدم فقدان أي مطابقة."""
    opts = opts or DEFAULT
    base = normalize(text, opts)
    variants = [base]
    # الشكل الإملائي: الألف الخنجرية تُحسب ألفاً كاملة (ٱلْكِتَٰبِ ← الكتاب)
    alt = normalize(text, NormOptions(**{**opts.__dict__, "khanjariyya_as_alef": True}))
    if alt != base:
        variants.append(alt)
    # الشكل مع إبقاء الألف الخنجرية محذوفة أصلاً (وارد)
    if "\u0670" in text:
        v3 = normalize(text, NormOptions(**{**opts.__dict__, "khanjariyya_as_alef": False,
                                            "strip_tashkeel": True}))
        if v3 not in variants:
            variants.append(v3)
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out


# --------------------------------------------------------------------------
# 3) بكوولتر (ترميز مجموعة ليدز الصرفية)
# --------------------------------------------------------------------------

BW2AR = {
    "'": "\u0621", "|": "\u0622", ">": "\u0623", "&": "\u0624", "<": "\u0625",
    "}": "\u0626", "{": "\u0671", "A": "\u0627",
    "b": "\u0628", "p": "\u0629", "t": "\u062a",
    "v": "\u062b", "j": "\u062c", "H": "\u062d", "x": "\u062e", "d": "\u062f",
    "*": "\u0630", "r": "\u0631", "z": "\u0632", "s": "\u0633", "$": "\u0634",
    "S": "\u0635", "D": "\u0636", "T": "\u0637", "Z": "\u0638", "E": "\u0639",
    "g": "\u063a", "_": TATWEEL, "f": "\u0641", "q": "\u0642", "k": "\u0643",
    "l": "\u0644", "m": "\u0645", "n": "\u0646", "h": "\u0647", "w": "\u0648",
    "Y": "\u0649", "y": "\u064a", "F": "\u064b", "N": "\u064c", "K": "\u064d",
    "a": "\u064e", "i": "\u0650", "u": "\u064f", "o": "\u0652", "~": "\u0651",
    "`": "\u0670", "^": "\u0653", "#": "\u0654", ".": SMALL_WAW, ",": SMALL_YEH,
    "@": "\u06df", "[": "\u06e2", "]": "\u06ed",
}

# رموز ترميز المجموعة لا تقابل حرفاً عربياً: تُسقَط عند بناء الهيكل الصرفي.
BW_MARKS = set("!\"%&'*+,-.:;<>@[]^_`{}|~o")


def buckwalter_to_arabic(bw: str, keep_marks: bool = True) -> str:
    """تحويل نص بكوولتر إلى حروف عربية (مع الحركات إن طُلب)."""
    out = []
    for ch in bw:
        ar = BW2AR.get(ch)
        if ar is None:
            continue          # رموز أحرف لاتينية أو رموز ترميز لا مقابل عربي لها
        out.append(ar)
    text = "".join(out)
    if not keep_marks:
        text = "".join(c for c in text if classify(c) == "letter")
    return unicodedata.normalize("NFC", text)


def buckwalter_skeleton(bw: str) -> str:
    """هيكل حروف من بكوولتر — يُستخدم لمحاذاة مجموعة ليدز مع نص تنزيل."""
    return skeleton(buckwalter_to_arabic(bw, keep_marks=False))


# --------------------------------------------------------------------------
# 4) إحصاءات الحروف والكلمات
# --------------------------------------------------------------------------

@dataclass
class TextStats:
    letters: int = 0            # عدد الحروف (الرسم)
    diacritics: int = 0         # عدد الحركات
    quran_marks: int = 0        # علامات الوقف والأرقام
    tatweel: int = 0
    chars: int = 0              # كل المحارف
    distinct_letters: set = field(default_factory=set)
    by_diacritic: dict = field(default_factory=dict)
    by_letter: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "letters": self.letters,
            "diacritics": self.diacritics,
            "quran_marks": self.quran_marks,
            "tatweel": self.tatweel,
            "chars": self.chars,
            "distinct_letters": len(self.distinct_letters),
            "by_diacritic": dict(sorted(self.by_diacritic.items(), key=lambda x: -x[1])),
            "by_letter": dict(sorted(self.by_letter.items(), key=lambda x: -x[1])),
        }


def text_stats(text: str) -> TextStats:
    st = TextStats()
    for ch in text:
        st.chars += 1
        k = classify(ch)
        if k == "letter":
            st.letters += 1
            st.distinct_letters.add(normalize(ch, NormOptions(strip_hamza=False)))
            st.by_letter[ch] = st.by_letter.get(ch, 0) + 1
        elif k == "diacritic":
            st.diacritics += 1
            n = diacritic_name(ch)
            st.by_diacritic[n] = st.by_diacritic.get(n, 0) + 1
        elif k == "quran_mark":
            st.quran_marks += 1
        elif k == "tatweel":
            st.tatweel += 1
    return st


def letters_only(text: str) -> str:
    """استخراج الحروف فقط (بلا حركات ولا علامات)."""
    return "".join(ch for ch in text if classify(ch) == "letter")


def has_diacritics(text: str) -> bool:
    """هل يحوي النص أي حركة (تشكيل)؟"""
    return any(classify(ch) == "diacritic" for ch in text)


# حساب الجُمّل (قيمة الحروف العددية — المشهور: أبجد هوز…)
ABJAD = {
    "\u0627": 1, "\u0623": 1, "\u0625": 1, "\u0622": 1, "\u0671": 1, "\u0621": 1,
    "\u0628": 2, "\u062c": 3, "\u062f": 4, "\u0647": 5, "\u0629": 5,
    "\u0648": 6, "\u0624": 6, "\u0632": 7, "\u062d": 8, "\u0637": 9,
    "\u064a": 10, "\u0649": 10, "\u0626": 10, "\u0643": 20, "\u0644": 30,
    "\u0645": 40, "\u0646": 50, "\u0633": 60, "\u0639": 70, "\u0641": 80,
    "\u0635": 90, "\u0642": 100, "\u0631": 200, "\u0634": 300, "\u062a": 400,
    "\u062b": 500, "\u062e": 600, "\u0630": 700, "\u0636": 800, "\u0638": 900,
    "\u063a": 1000,
}


def abjad_value(text: str) -> int:
    """حساب الجُمّل الكبير (يعتمد الحروف دون تشكيل)."""
    return sum(ABJAD.get(ch, 0) for ch in letters_only(text))


# --------------------------------------------------------------------------
# 5) المطابقة الحساسة للتشكيل
# --------------------------------------------------------------------------

def _pairs_with_marks(word: str) -> list[tuple[str, frozenset]]:
    """يرجع لكل حرف: (الحرف المطبَّع، مجموعة الحركات التي عليه)."""
    out = []
    pending: list[str] = []
    for ch in word:
        k = classify(ch)
        if k == "letter":
            out.append((normalize(ch, NormOptions(strip_hamza=False)), frozenset()))
            pending = []
        elif k == "diacritic":
            if out:
                base, s = out[-1]
                out[-1] = (base, s | {diacritic_name(ch)})
    return out


def matches_with_tashkeel(word: str, query: str) -> bool:
    """مطابقة دقيقة تُلزم وجود كل حركة في الاستعلام بنفس الموضع في الكلمة."""
    w = _pairs_with_marks(word)
    q = _pairs_with_marks(query)
    if len(q) > len(w):
        return False
    for i in range(len(w) - len(q) + 1):
        ok = True
        for j in range(len(q)):
            if w[i + j][0] != q[j][0] or not q[j][1].issubset(w[i + j][1]):
                ok = False; break
        if ok:
            return True
    return False
