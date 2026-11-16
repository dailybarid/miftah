"""
اختبارات طبقة العربية (app/arabic.py) — لا تحتاج قاعدة البيانات.

التشغيل:
    python3 -m unittest discover -s tests -v
    python3 tests/test_arabic.py          # مباشرة أيضاً
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.arabic import (  # noqa: E402
    NormOptions, abjad_value, buckwalter_skeleton, buckwalter_to_arabic,
    has_diacritics, letters_only, normalize, search_variants,
)


class TestNormalization(unittest.TestCase):
    """التطبيع: حذف التشكيل وتوحيد الأشكال، مع خيار الألف الخنجرية."""

    def test_strip_tashkeel(self):
        self.assertEqual(normalize("مُحَمَّدٌ", NormOptions(strip_tashkeel=True)), "محمد")

    def test_unify_alef_variants(self):
        # آ أ إ ٱ ← ا
        for w in ["أحمد", "إبراهيم", "آمنوا", "ٱلْحَمْدُ"]:
            n = normalize(w, NormOptions(strip_tashkeel=True))
            self.assertNotIn("أ", n)
            self.assertNotIn("إ", n)
            self.assertNotIn("آ", n)
            self.assertNotIn("\u0671", n)

    def test_unify_ya_and_ta_marbuta(self):
        self.assertEqual(normalize("مُوسَى", NormOptions(strip_tashkeel=True)), "موسي")
        self.assertEqual(normalize("رَحْمَة", NormOptions(strip_tashkeel=True)), "رحمه")

    def test_unify_can_be_disabled(self):
        n = normalize("مُوسَى", NormOptions(strip_tashkeel=True, unify_ya=False))
        self.assertIn("\u0649", n)  # الألف المقصورة باقية

    def test_khanjariyya_modes(self):
        """الألف الخنجرية: تُحذف افتراضاً، وتُحسب ألفاً عند الطلب."""
        self.assertEqual(normalize("ٱلْكِتَٰبِ"), "الكتب")
        self.assertEqual(normalize("ٱلْكِتَٰبِ", NormOptions(khanjariyya_as_alef=True)), "الكتاب")
        self.assertEqual(normalize("ٱلرَّحْمَٰنِ"), "الرحمن")
        self.assertEqual(normalize("ٱلرَّحْمَٰنِ", NormOptions(khanjariyya_as_alef=True)), "الرحمان")

    def test_search_variants_cover_all_orthographies(self):
        """الاستعلام الإملائي يجب أن يولّد نسخة الرسم العثماني (حذف الألف الخنجرية)."""
        v = search_variants("ٱلْكِتَٰبِ")
        self.assertIn("الكتب", v)          # الرسم العثماني
        self.assertIn("الكتاب", v)         # الشكل الإملائي
        self.assertEqual(len(v), len(set(v)), "لا تكرار في النسخ")

    def test_letters_only_drops_marks_and_marks_of_waqf(self):
        """letters_only تُبقي الحرف كما هو (بما فيه ٱ) وتُسقط الحركات وعلامات الوقف؛
        وتوحيد الهمزات وظيفة normalize."""
        self.assertEqual(letters_only("ٱلْحَمْدُ ۖ لِلَّهِ"), "ٱلحمدلله")
        self.assertEqual(letters_only(normalize("ٱلْحَمْدُ ۖ لِلَّهِ")), "الحمدلله")

    def test_has_diacritics(self):
        self.assertFalse(has_diacritics("الرحمن"))
        self.assertTrue(has_diacritics("ٱلرَّحْمَٰنِ"))
        self.assertTrue(has_diacritics("مُحَمَّدٌ"))

    def test_tatweel_is_removed(self):
        self.assertEqual(normalize("الـمـلـك", NormOptions(strip_tashkeel=True)), "الملك")

    def test_empty_and_spaces(self):
        self.assertEqual(normalize("   "), "")
        self.assertEqual(letters_only(""), "")


class TestBuckwalter(unittest.TestCase):
    """فك ترميز بكوولتر — أساس محاذاة مجموعة ليدز الصرفية."""

    def test_basic_decode(self):
        self.assertEqual(buckwalter_to_arabic("AlrHmn"), "الرحمن")
        self.assertEqual(buckwalter_to_arabic("AlktAb"), "الكتاب")

    def test_alef_wasla_brace(self):
        """{ = U+0671 (ألف الوصل) — كان غيابه يُفسد المحاذاة كلها.
        وفي بكوولتر: a = الفتحة و A = الألف."""
        self.assertEqual(buckwalter_to_arabic("{"), "\u0671")
        self.assertEqual(buckwalter_to_arabic("{ll~ah"), "\u0671للَّه")  # ٱللَّه
        self.assertEqual(buckwalter_to_arabic("aA"), "\u064e\u0627")     # فتحة + ألف

    def test_hamza_letters(self):
        self.assertEqual(buckwalter_to_arabic(">"), "أ")
        self.assertEqual(buckwalter_to_arabic("<"), "إ")
        self.assertEqual(buckwalter_to_arabic("&"), "ؤ")
        self.assertEqual(buckwalter_to_arabic("}"), "ئ")

    def test_skeleton_matches_uthmani_letters(self):
        """هيكل بكوولتر = حروف الكلمة في الرسم العثماني:
        • الكلمات التي رسمها العثماني بلا ألف خنجرية (الرحمن، الصلاة) تساوي التطبيع الافتراضي.
        • الكلمات التي فيها ألف خنجرية (الكتاب) تساوي التطبيع بخيار khanjariyya_as_alef
          لأن بكوولتر يكتبها ألفاً صريحة (A)."""
        hanj = NormOptions(khanjariyya_as_alef=True)
        self.assertEqual(buckwalter_skeleton("AlrHmn"), letters_only(normalize("ٱلرَّحْمَٰنِ")))
        self.assertEqual(buckwalter_skeleton("AlSlwh"), letters_only(normalize("ٱلصَّلَوٰةَ")))
        self.assertEqual(buckwalter_skeleton("AlktAb"), letters_only(normalize("ٱلْكِتَٰبِ", hanj)))
        self.assertNotEqual(buckwalter_skeleton("AlktAb"), letters_only(normalize("ٱلْكِتَٰبِ")))

    def test_skeleton_is_letters_only(self):
        """الهيكل لا يحوي حركات ولا علامات وقف (وإلا فسدت المحاذاة)."""
        sk = buckwalter_skeleton("Alr~aHoma`ni")
        self.assertEqual(sk, "الرحمن")
        self.assertFalse(has_diacritics(sk))


class TestAbjad(unittest.TestCase):
    """حساب الجُمّل — قيم مرجعية معروفة."""

    def test_known_values(self):
        self.assertEqual(abjad_value("ا"), 1)
        self.assertEqual(abjad_value("بسم"), 102)      # ب2 + س60 + م40
        self.assertEqual(abjad_value("الله"), 66)      # ا1 + ل30 + ل30 + ه5
        self.assertEqual(abjad_value("مُحَمَّد"), 92)   # الحركات لا تُحسب

    def test_basmala_total(self):
        """بسم الله الرحمن الرحيم = 786 (قيمة مشهورة)."""
        total = sum(abjad_value(w) for w in ["بسم", "الله", "الرحمن", "الرحيم"])
        self.assertEqual(total, 786)

    def test_non_letters_are_zero(self):
        self.assertEqual(abjad_value("ۖ 123"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
