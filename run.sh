#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# مِفتاح — تشغيل محرك بحث القرآن الكريم
#   الاستخدام:  ./run.sh [منفذ]        (الافتراضي 8770)
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8770}"
DB="data/quran.db"

echo "← مِفتاح: محرك بحث وتحليل القرآن الكريم"

# 1) التحقّق من الاعتماديات (FastAPI + Uvicorn — لا مكتبات أخرى)
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "! مكتبتا fastapi و uvicorn مطلوبتان لتشغيل الخادم. ثبّتهما بالأمر:"
  echo "    python3 -m pip install --user fastapi uvicorn"
  echo "  (منطق المحرك نفسه يعتمد على مكتبة بايثون القياسية فقط ولا يحتاج أي تثبيت)"
  exit 1
fi

# 2) بناء قاعدة البيانات إن لم تكن موجودة
if [ ! -f "$DB" ]; then
  echo "← بناء قاعدة البيانات من النصوص المصدرية (قد يستغرق دقيقة)…"
  python3 scripts/build_db.py
fi

# 3) بناء المحاور الموضوعية إن لم تكن مبنية
python3 - <<'PY' 2>/dev/null || true
import sqlite3, sys
db = sqlite3.connect("data/quran.db")
try:
    db.execute("SELECT 1 FROM topic LIMIT 1")
except sqlite3.OperationalError:
    print("← بناء المحاور الموضوعية…")
    import subprocess
    subprocess.run([sys.executable, "scripts/build_topics.py"], check=False)
PY

echo "← الخادم يعمل على:  http://127.0.0.1:${PORT}/"
echo "  التوثيق التفاعلي:  http://127.0.0.1:${PORT}/api/docs"
echo "  للإيقاف: Ctrl+C"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
