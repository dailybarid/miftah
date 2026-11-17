# NOTICE — third-party components, data and licences

This repository redistributes material that is **not** covered by the project's own licence. Each
item below keeps its own terms; the list is exhaustive for the files committed here.

## Corpus data (`data/sources/`, 8.2 MB, committed)

These files are redistributed **verbatim and unmodified**, with attribution, as their licences require.

| File | Origin | Licence | Requirements met |
|---|---|---|---|
| `quran-uthmani.txt` | [Tanzil](https://tanzil.net) | CC BY-ND 3.0 | attribution; text unmodified; distributed under the same terms |
| `quran-simple-clean.txt` | [Tanzil](https://tanzil.net) | CC BY-ND 3.0 | as above |
| `quranic-corpus-morphology-0.4.txt` | [Quranic Arabic Corpus v0.4](https://corpus.quran.com), University of Leeds (Kais Dukes) | GPL | source text shipped in full; this project's licence (GPL-3.0-or-later) is GPL-compatible |
| `quran-data.xml` | [Tanzil](https://tanzil.net) | CC BY | attribution |

`data/quran.db` is **not** committed: it is a locally built index produced from the files above by
`scripts/build_db.py`. The SHA-256 of every source file is recorded in `data/build_report.json`.

Because the morphology corpus is GPL, the derived database and any redistribution of it must remain
GPL-compatible. If you redistribute a built database, keep this notice with it.

## Fonts (`web/fonts/`)

| Font | Licence |
|---|---|
| KFGQPC HAFS Uthmanic Script (version 0.18) | KFGQPC electronic end-user licence agreement — free of cost to **use, copy and distribute**; the font may **not** be sold, modified, altered, translated, reverse engineered or decompiled, and is provided "as is". Full text: [`web/fonts/LICENSE-KFGQPC.txt`](web/fonts/LICENSE-KFGQPC.txt) |
| Amiri Quran · IBM Plex Sans Arabic · Reem Kufi · Aref Ruqaa · Noto Naskh Arabic | SIL Open Font Licence 1.1 (Google Fonts releases). The licence text of each family, with the copyright notice it carries, is reproduced in full in [`web/fonts/LICENSE-OFL.txt`](web/fonts/LICENSE-OFL.txt). |

The KFGQPC font is shipped in its original, unmodified form; its agreement is reproduced in full
beside it. It is an aggregated asset: the font's licence does **not** extend to the code in this
repository, and the GPL grant below does **not** extend to the font.

The five fonts under the SIL Open Font Licence are also shipped unmodified. OFL 1.1 requires the
licence and the copyright notice to accompany every copy, so both travel with them in
[`web/fonts/LICENSE-OFL.txt`](web/fonts/LICENSE-OFL.txt) — five verbatim texts, one per family,
taken from `github.com/google/fonts`.

## JavaScript

| Library | Licence |
|---|---|
| [D3](https://d3js.org) 7.9.0 (`web/vendor/d3.min.js`, unmodified) | ISC |

## Network service (not redistributed)

Recitation audio is streamed on demand from `everyayah.com`. No audio is stored in this repository.
Use of that service is subject to its own terms.

## Scope of the project licence

Copyright (C) 2026 KHALED. The source code of this application (`app/`, `scripts/`, `web/js/`,
`web/css/`, `web/index.html`, `tests/`, `run.sh`, documentation) is licensed under the **GNU General
Public License, version 3 or later** — see [`LICENSE`](LICENSE). Third-party components listed above
are licensed by their own terms and are excluded from that grant.
