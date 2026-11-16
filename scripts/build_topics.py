#!/usr/bin/env python3
"""
build_topics.py — استخراج محاور موضوعية من تزامن الجذور
========================================================
يقرأ جدول root_ayah (تزامن الجذور مع الآيات) ويبني من إحصاءات التزامن
رسمًا غير موجه مرجَّح الوزن بين الجذور، ثم يكتشف فيه مجتمعات ذات معنى
بخوارزمية «الدمج الجشع للأهمية المجتمعية» (Greedy Modularity / CNM)
مع مُعامِل دقة (resolution) وحدٍّ أعلى صارم لحجم المحور، ويكتب النتيجة
في جدولين جديدين: topic و topic_root، دون المساس بأي جدول آخر.

لماذا لا «انتشار التسميات»؟
    انتشار التسميات على رسم جذر-جذر كثيف ينتهي دائمًا إلى كتلة واحدة
    (جُرِّب: محور واحد يبتلع ٨٣٦ جذرًا حتى مع رفع حدّ التزامن). الدمج
    الجشع يزيد دالة هدف صريحة، ومعامل الدقة + الحدّ الأعلى يمنعان
    الاندماج الكامل ويضمنان محاور متعددة محدودة الحجم.

الخوارزمية:
  1) تحميل كل الأزواج (root_id, ayah_id) من root_ayah مع إزالة التكرار
     (الجذر نفسه قد يتكرر داخل الآية بلفظين، فتتكرر الأسطر).
     الوزن الخام(a,b) = عدد الآيات التي تحوي الجذرَين معًا.
  2) تقليم الحواف: تبقى الحافّة إذا (أ) التزامن >= --min-weight،
     (ب) PMI = log2((w*N)/(na*nb)) > --min-pmi، (ج) كانت الحافّة من
     أقوى --top-k جوارٍ لأحد الطرفين على الأقل — فلا تربط الجذور
     الشائعة الرسم كله.
     وزن الحافّة النهائي = PMI (لا التزامن الخام).
  3) الدمج الجشع: يبدأ كل جذر محورًا وحده، ثم يُدمج زوج المحاور الذي
     يزيد الأهمية المجتمعية:
         ΔQ = w_ab/m − γ·(K_a·K_b)/(2m²)
     حيث m = مجموع أوزان الحواف، K = مجموع درجات الجذور في المحور،
     γ = --resolution. يُمنع أي دمج يُنتج محورًا أكبر من --max-size،
     ويُمنع الدمج إذا كانت ΔQ <= 0. التعادل يُحسم بأصغر معرّف محور
     (حتمي بالكامل، بلا عشوائية).
  4) إسقاط وإعادة إنشاء جدولَي topic و topic_root فقط:
        topic(id, label, weight, size)
        topic_root(topic_id, root_id, weight, PRIMARY KEY(topic_id,root_id))
     topic.weight = مجموع count الجذور الأعضاء؛ size = عدد الأعضاء.
     topic_root.weight = count الجذر نفسه.
     label = تسمية عربية قصيرة: قيم arabic لأعلى 3-5 جذور أعضاء.
     تُستبعد المحاور التي تقلّ عن --min-size، ولا تظهر جذورها في
     topic_root.

الاستخدام:
    python3 scripts/build_topics.py [--db data/quran.db] [--min-weight 3]
                                    [--min-pmi 0.0] [--top-k 25]
                                    [--resolution 4.0] [--max-size 40]
                                    [--min-size 4]

القيم الافتراضية مُعايَرة على قاعدة بيانات المشروع: ٧٥ محورًا، أكبر محور
٣٤ جذرًا، تغطية ≈ ٥١٪ من الجذور (الباقي جذور نادرة لا تكفي لتكوين محور).
"""
from __future__ import annotations

import argparse
import collections
import heapq
import json
import math
import sqlite3
import time

# مسارات المشروع تُشتق من مكان السكربت حتى يعمل من أي دليل عمل.
_HERE = __file__.rsplit("/", 1)[0]            # .../scripts
_ROOT = _HERE.rsplit("/", 1)[0]               # جذور المشروع
DEFAULT_DB = _ROOT + "/data/quran.db"
DEFAULT_REPORT = _ROOT + "/data/topics_report.json"


# ---------------------------------------------------------------------------
# القراءة وبناء الرسم
# ---------------------------------------------------------------------------

def load_graph(db: sqlite3.Connection) -> dict:
    """يقرأ root_ayah و root: آيات كل جذر، التزامن الخام، الأوزان والتسميات."""
    per_ayah: dict[int, set[int]] = collections.defaultdict(set)
    for root_id, ayah_id in db.execute("SELECT root_id, ayah_id FROM root_ayah"):
        per_ayah[ayah_id].add(root_id)

    ayah_count: collections.Counter = collections.Counter()
    for roots in per_ayah.values():
        for r in roots:
            ayah_count[r] += 1

    # التزامن الخام = عدد الآيات التي تحوي الجذرَين معًا.
    cooccur: collections.Counter = collections.Counter()
    for roots in per_ayah.values():
        rs = sorted(roots)
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                cooccur[(rs[i], rs[j])] += 1

    root_count: dict[int, int] = {}
    root_arabic: dict[int, str] = {}
    for rid, arabic, cnt in db.execute("SELECT id, arabic, count FROM root"):
        root_count[rid] = cnt
        root_arabic[rid] = arabic

    return {
        "ayah_count": ayah_count,
        "cooccur": cooccur,
        "root_count": root_count,
        "root_arabic": root_arabic,
        "total_ayahs": db.execute("SELECT COUNT(*) FROM ayah").fetchone()[0],
    }


def build_edges(data: dict, min_weight: int, min_pmi: float,
                top_k: int) -> tuple[dict, dict]:
    """يقلم الحواف ويعيد (الأوزان، الدرجات).

    الأوزان: dict[(a,b)] = PMI لحافّة مُقلمة؛ الدرجات: dict[node] = مجموع أوزانها.
    """
    N = data["total_ayahs"]
    na = data["ayah_count"]
    strong: dict[int, list[tuple[float, int]]] = collections.defaultdict(list)

    for (a, b), w in data["cooccur"].items():
        if w < min_weight:
            continue
        pmi = math.log2((w * N) / (na[a] * na[b]))
        if pmi <= min_pmi:
            continue
        strong[a].append((pmi, b))
        strong[b].append((pmi, a))

    # الاحتفاظ بالحواف التي دخلت قائمة أقوى جيران أحد الطرفين (top-k).
    weights: dict[tuple[int, int], float] = {}
    degree: collections.Counter = collections.Counter()
    for a, lst in strong.items():
        lst.sort(key=lambda x: (-x[0], x[1]))
        for pmi, b in lst[:top_k]:
            key = (a, b) if a < b else (b, a)
            if key not in weights or pmi > weights[key]:
                weights[key] = pmi
    for (a, b), w in weights.items():
        degree[a] += w
        degree[b] += w
    return weights, dict(degree)


# ---------------------------------------------------------------------------
# الدمج الجشع للأهمية المجتمعية (حتمي)
# ---------------------------------------------------------------------------

def greedy_modularity(weights: dict[tuple[int, int], float],
                      degree: dict[int, float],
                      resolution: float,
                      max_size: int,
                      max_merges: int = 100_000) -> list[list[int]]:
    """يعيد قائمة محاور، كل محور <= max_size جذرًا.

    ΔQ بين محورين مجاورين = w_ab/m − γ·(K_a·K_b)/(2m²)، والدمج يُقبل
    إذا كان ΔQ > 0 ولم يتجاوز حجم الناتج max_size. كومات كسولة (lazy heap)
    مع عدّاد إصدارات لكل محور لإبطال الإدخالات القديمة.
    """
    m = sum(weights.values())
    if m <= 0:
        return [[n] for n in sorted(degree)]

    members: dict[int, list[int]] = {n: [n] for n in sorted(degree)}
    K: dict[int, float] = {n: float(degree[n]) for n in members}
    version: dict[int, int] = {n: 0 for n in members}

    # w_ab: أوزان الحواف بين المحاور (تبدأ بحواف العقد نفسها).
    inter: dict[int, dict[int, float]] = collections.defaultdict(dict)
    for (a, b), w in weights.items():
        if a == b:
            continue
        inter[a][b] = w
        inter[b][a] = w

    def dq(a: int, b: int) -> float:
        wab = inter.get(a, {}).get(b, 0.0)
        ka, kb = K[a], K[b]
        return wab / m - resolution * (ka * kb) / (2.0 * m * m)

    heap: list[tuple[float, int, int, int, int]] = []
    for a in sorted(inter):
        for b in sorted(inter[a]):
            if a < b:
                heapq.heappush(heap, (-dq(a, b), a, b, version[a], version[b]))

    merges = 0
    while heap and merges < max_merges:
        negq, a, b, va, vb = heapq.heappop(heap)
        if a not in members or b not in members:
            continue
        if version[a] != va or version[b] != vb:
            continue                      # إدخال قديم بعد دمج سابق
        if -negq <= 0.0:
            break                         # لم تبقَ أي زيادة موجبة
        if len(members[a]) + len(members[b]) > max_size:
            continue                      # حدّ الحجم الصارم

        # الدمج: الأصغر يُدمج في الأكبر (تعادل → أصغر معرّف) لضمان الحتمية.
        if (len(members[a]), a) > (len(members[b]), b):
            a, b = b, a
        members[a].extend(members[b])
        K[a] += K[b]
        version[a] += 1
        del members[b], K[b], version[b]

        # تحديث الجوار بين المحاور.
        merged_neigh = {}
        for x, w in inter.pop(b, {}).items():
            if x == a or x not in members:
                continue
            merged_neigh[x] = merged_neigh.get(x, 0.0) + w
            inter[x].pop(b, None)
        for x, w in merged_neigh.items():
            inter[a][x] = inter[a].get(x, 0.0) + w
            inter[x][a] = inter[x].get(a, 0.0) + w
        for x in list(inter.get(a, {})):
            if x not in members:
                del inter[a][x]

        for x in sorted(inter.get(a, {})):
            heapq.heappush(heap, (-dq(a, x), min(a, x), max(a, x),
                                  version[min(a, x)], version[max(a, x)]))
        merges += 1

    return sorted((sorted(v) for v in members.values()), key=lambda c: (-len(c), c[0]))


def split_oversized(clusters: list[list[int]],
                    weights: dict[tuple[int, int], float],
                    max_size: int) -> list[list[int]]:
    """شبكة أمان: يقسم أي محور تجاوز الحدّ إلى أجزاء متصلة <= max_size.

    يُستخدم فقط إذا لم يُنفَّذ الدمج بحدّ الحجم (لا يحدث عمليًا)، لكنه
    يضمن الشرط بنيويًا: كل جزء متصل داخليًا حيث أمكن.
    """
    out: list[list[int]] = []
    for c in clusters:
        if len(c) <= max_size:
            out.append(c)
            continue
        node_set = set(c)
        adj: dict[int, list[int]] = {n: [] for n in c}
        for (a, b) in weights:
            if a in node_set and b in node_set:
                adj[a].append(b)
                adj[b].append(a)
        seen: set[int] = set()
        for start in c:
            if start in seen:
                continue
            comp: list[int] = []
            stack = [start]
            seen.add(start)
            while stack:
                n = stack.pop()
                comp.append(n)
                for nb in adj[n]:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            for i in range(0, len(comp), max_size):
                out.append(sorted(comp[i:i + max_size]))
    return out


# ---------------------------------------------------------------------------
# الكتابة
# ---------------------------------------------------------------------------

def write_topics(db: sqlite3.Connection, data: dict,
                 communities: list[list[int]],
                 min_size: int,
                 weights: dict[tuple[int, int], float] | None = None,
                 ) -> tuple[int, int]:
    """يسقط ويعيد إنشاء topic و topic_root فقط؛ يعيد (عدد المحاور، الجذور المخصَّصة).

    التسمية تُبنى من أعلى الجذور بالوزن الداخلي (مجموع أوزان روابطها داخل
    المحور) لا من أعلى الجذور تكرارًا في المصحف — فالجذور الشائعة («اله»،
    «قول») تتكرر في كل محور ولا تُميّز شيئًا.
    """
    rc, ra = data["root_count"], data["root_arabic"]
    kept = [m for m in communities if len(m) >= min_size]
    kept.sort(key=lambda m: (-sum(rc[r] for r in m), m[0]))

    def internal_strength(members: list[int]) -> dict[int, float]:
        """مجموع أوزان روابط كل جذر داخل محوره."""
        ms = set(members)
        st: collections.Counter = collections.Counter()
        if weights:
            for (a, b), w in weights.items():
                if a in ms and b in ms:
                    st[a] += w
                    st[b] += w
        return st

    db.execute("DROP TABLE IF EXISTS topic")
    db.execute("DROP TABLE IF EXISTS topic_root")
    db.execute("CREATE TABLE topic(id INTEGER PRIMARY KEY, label TEXT,"
               " weight REAL, size INTEGER)")
    db.execute("CREATE TABLE topic_root(topic_id INTEGER, root_id INTEGER,"
               " weight REAL, PRIMARY KEY(topic_id, root_id))")

    topic_rows, tr_rows = [], []
    roots_assigned = 0
    for tid, members in enumerate(kept, start=1):
        st = internal_strength(members)
        # الترتيب للتسمية: الأقوى ربطًا داخل المحور، ثم الأكثر تكرارًا.
        label_order = sorted(members, key=lambda r: (-st.get(r, 0.0), -rc[r], r))
        seen, parts = set(), []
        for r in label_order[:6]:
            name = ra.get(r, "")
            if name and name not in seen:
                seen.add(name)
                parts.append(name)
            if len(parts) == 5:
                break
        topic_rows.append((tid, " · ".join(parts),
                           float(sum(rc[r] for r in members)), len(members)))
        members_sorted = sorted(members, key=lambda r: (-st.get(r, 0.0), -rc[r], r))
        tr_rows.extend((tid, r, float(rc[r])) for r in members_sorted)
        roots_assigned += len(members)

    db.executemany("INSERT INTO topic(id,label,weight,size) VALUES (?,?,?,?)", topic_rows)
    db.executemany("INSERT INTO topic_root(topic_id,root_id,weight) VALUES (?,?,?)", tr_rows)
    db.commit()
    return len(topic_rows), roots_assigned


# ---------------------------------------------------------------------------
# الدخول
# ---------------------------------------------------------------------------

def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser(
        description="استخراج محاور موضوعية من تزامن الجذور إلى topic/topic_root")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--min-weight", type=int, default=3,
                    help="أدنى تزامن (آيات مشتركة) لبقاء حافّة")
    ap.add_argument("--min-pmi", type=float, default=0.0,
                    help="أدنى PMI لبقاء حافّة (يُقصي الجذور الشائعة)")
    ap.add_argument("--top-k", type=int, default=25,
                    help="عدد أقوى جيران يُحتفظ بهم لكل جذر")
    ap.add_argument("--resolution", type=float, default=4.0,
                    help="مُعامِل الدقة γ: أكبر ⇒ محاور أكثر وأصغر")
    ap.add_argument("--max-size", type=int, default=40,
                    help="الحدّ الأعلى لعدد جذور المحور الواحد (صارم)")
    ap.add_argument("--min-size", type=int, default=4,
                    help="أدنى عدد جذور لمحور ليُحتسب")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    print("جارٍ قراءة أزواج الجذر-الآية من root_ayah ...")
    data = load_graph(db)
    print(f"آيات: {data['total_ayahs']} | جذور لها آيات: {len(data['ayah_count'])} "
          f"| أزواج تزامن خام: {len(data['cooccur'])}")

    print(f"جارٍ تقليم الحواف (تزامن ≥ {args.min_weight}، PMI > {args.min_pmi}، top-{args.top_k}) ...")
    weights, degree = build_edges(data, args.min_weight, args.min_pmi, args.top_k)
    print(f"حواف مُقلمة: {len(weights)} | عقد: {len(degree)} | "
          f"مجموع الأوزان (PMI): {sum(weights.values()):.1f}")

    print(f"جارٍ الدمج الجشع (γ={args.resolution}، الحدّ الأعلى {args.max_size}) ...")
    clusters = greedy_modularity(weights, degree, args.resolution, args.max_size)
    clusters = split_oversized(clusters, weights, args.max_size)
    sizes = sorted((len(c) for c in clusters), reverse=True)
    print(f"محاور قبل الترشيح: {len(clusters)} | أكبر محور: {sizes[0] if sizes else 0} جذرًا")
    print(f"توزيع الأحجام: {sizes[:25]}{' …' if len(sizes) > 25 else ''}")

    print(f"جارٍ الكتابة إلى topic و topic_root (أدنى حجم {args.min_size}) ...")
    n_topics, roots_assigned = write_topics(db, data, clusters, args.min_size, weights)

    seconds = time.time() - t0
    dist = [r["size"] for r in db.execute("SELECT size FROM topic ORDER BY size DESC")]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topics": n_topics,
        "roots_assigned": roots_assigned,
        "roots_with_ayat": len(data["ayah_count"]),
        "coverage": round(roots_assigned / max(1, len(data["ayah_count"])) * 100, 2),
        "min_weight": args.min_weight,
        "min_pmi": args.min_pmi,
        "top_k": args.top_k,
        "resolution": args.resolution,
        "max_size": args.max_size,
        "min_size": args.min_size,
        "size_distribution": dist,
        "seconds": round(seconds, 3),
        "top": [],
    }
    for t in db.execute("SELECT label, size, weight FROM topic "
                        "ORDER BY weight DESC LIMIT 10"):
        report["top"].append({"label": t["label"], "size": t["size"],
                              "weight": t["weight"]})
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    db.close()

    print("-" * 64)
    print(f"تمّ: {n_topics} محورًا موضوعيًا | {roots_assigned} جذرًا مخصَّصًا "
          f"({report['coverage']}%) | {seconds:.2f} ثانية")
    print(f"أكبر محور: {dist[0] if dist else 0} جذرًا | أصغر محور مقبول: {dist[-1] if dist else 0}")
    print(f"تقرير: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
