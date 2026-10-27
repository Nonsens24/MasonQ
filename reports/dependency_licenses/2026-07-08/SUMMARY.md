# MasonQ — Third-party dependency license review

**Report date:** 2026-07-08
**Product:** MasonQ / VEIL Quantum cloak layer
**Product license:** Proprietary
**Distribution model:** Python package, no C static-linking
**Python interpreter:** CPython 3.12
**Report scope:** All packages that MasonQ actually imports, directly or transitively (41 packages total).

## 1. Executive summary

MasonQ's runtime dependency graph contains **41 third-party Python packages** (40 transitive + `masonq` itself). Every one of them ships under a permissive OSS license. There are **no GPL, no AGPL, no LGPL, no SSPL, no source-availability licenses, and no "commercial use restricted" licenses** in the tree.

Distribution requirements are limited to preserving **copyright notices** and **attribution text** in derivative distributions — the standard requirement of the Apache 2.0 / BSD / MIT family. Every LICENSE file for every dependency is bundled with this report under `attributions_full.txt` (532 KB, redistribution-ready).

Recommendation for legal: **cleared for proprietary distribution** subject to (a) shipping the attribution bundle alongside any binary release, and (b) not modifying any Apache-2.0 licensed file in a way that removes the required NOTICE preservation.

## 2. Notable findings

### 2.1 One package flagged for review — resolved

`tqdm 4.66.4` is dual-licensed **MIT + MPL 2.0**. Because it is dual-licensed, MasonQ is entitled to use it under either license. The MIT option imposes only attribution requirements identical to every other MIT-licensed dependency in the tree; the MPL requirement (share modifications to `tqdm.py` itself back upstream) is moot because MasonQ does not modify `tqdm`. **No further action required.**

The installed `tqdm` wheel did not bundle its LICENSE file (a minor packaging issue on the tqdm side), so a supplemental attribution note is included at `attributions_supplemental.txt`.

### 2.2 One package initially reported "UNKNOWN" — resolved

`graphix 0.3.5` was reported by `pip-licenses` as license-UNKNOWN because the maintainer did not populate the standard PyPI `License` classifier field. Direct inspection of the installed wheel confirms `graphix` is **Apache License 2.0**; the LICENSE file is bundled with the package under `graphix-0.3.5.dist-info/licenses/LICENSE`. Legal need not be concerned about this entry.

### 2.3 Packages outside masonq's tree that appeared in the raw scan

The raw `pip-audit` / `pip-licenses` sweeps run against the developer's conda environment surface a number of unrelated packages that share the interpreter but are **not** part of masonq's dependency graph (`pokete`, `scrap_engine` — GPL-3 games; various `langchain-*` packages; `pyzmq` LGPL; `gmpy2` LGPLv3+). These are development-machine noise and are not shipped with, imported by, or required by MasonQ. They are excluded from every table in this report, and Section 3 lists exactly the 41 packages that legal actually needs to review.

## 3. Dependency inventory

The full machine-readable table (name, version, license, author, homepage, license text) is in `masonq_licenses.csv`. A readable version is at `masonq_licenses.md`. A brief distribution by license category:

| License family | Count | Distribution-time obligation |
| --- | --- | --- |
| Apache License 2.0 | 12 | Preserve NOTICE files, retain copyright headers in redistributed source |
| BSD (2/3-Clause and BSD License) | 12 | Preserve copyright notice + list of contributors in binary distributions |
| MIT / MIT License | 10 | Preserve copyright notice |
| MIT + MPL 2.0 (dual) | 1 (`tqdm`) | MIT terms apply for MasonQ's use |
| Historical Permission Notice and Disclaimer (HPND) | 1 (`pillow`) | Preserve HPND copyright + disclaimer |
| PSF-style / Python-2.0 permissive | 4 | Preserve copyright notice |
| Combined permissive (Apache + BSD, etc.) | 1 | Follow either sub-license (both permissive) |

## 4. Attribution obligations MasonQ must fulfil at distribution time

When shipping any binary or source form of MasonQ to an external party:

1. **Include the attribution bundle.** The file `attributions_full.txt` in this report directory contains the exact LICENSE / NOTICE / COPYING text bundled by every dependency at install time (plus the supplemental note for `tqdm`). Ship this file alongside the MasonQ distribution — a top-level `THIRD_PARTY_LICENSES.txt` in the wheel is the conventional location.
2. **Do not remove NOTICE files.** Every Apache-2.0 dependency ships a `NOTICE` file; if any of them is modified or repackaged, the NOTICE text must be preserved in the modification.
3. **Do not sublicense.** MasonQ's proprietary license does not need to grant end users a license to the OSS dependencies; those come with their own licenses in the attribution bundle.
4. **No GPL / copyleft trigger.** Because no copyleft dependencies are present, MasonQ's proprietary source code is not required to be disclosed by any dependency's license.

## 5. Files in this report directory

| File | Purpose | Size |
| --- | --- | --- |
| `SUMMARY.md` | This document — the primary artifact for legal review | ~5 KB |
| `masonq_deps.txt` | Newline-separated list of every package in masonq's tree | ~500 B |
| `masonq_licenses.csv` | Machine-readable table: name, version, license, author, URL, full license text | ~700 KB |
| `masonq_licenses.md` | Human-readable version of the above table | ~7 KB |
| `masonq_tree.json` | Dependency tree in JSON (from `pipdeptree -p masonq --json`) | ~10 KB |
| `attributions_full.txt` | Concatenated LICENSE / NOTICE / COPYING files from every dependency — the redistribution-ready attribution bundle | ~530 KB |
| `attributions_supplemental.txt` | Supplemental attribution for `tqdm` (LICENSE not bundled in wheel) | ~1 KB |
| `licenses_full.csv` | Raw pip-licenses output for the *entire* developer environment (not filtered to masonq) — kept for auditability of the filtering step | ~730 KB |
| `licenses_table.md` | Raw pip-licenses markdown output for the entire dev env | ~130 KB |
| `licenses_summary.txt` | Raw pip-licenses summary output for the entire dev env | ~5 KB |

## 6. Sign-off checklist

- [ ] Legal has reviewed `SUMMARY.md` and confirmed no copyleft is present.
- [ ] Legal has confirmed the attribution model in Section 4 satisfies the university's IP policy.
- [ ] `attributions_full.txt` has been added to the distribution build under `THIRD_PARTY_LICENSES.txt`.
- [ ] A ticket has been opened to re-run this scan (a) before every external release and (b) whenever `pyproject.toml` changes.

## 7. How to reproduce this report

```bash
pip install pipdeptree pip-audit pip-licenses
cd MasonQ
scripts/scan_dependencies.sh   # (add-once helper, not yet checked in)
```

The manual sequence used to produce this report is documented in the "Suggested follow-ups" section of the developer's dependency-scan notes; the raw commands are:

```bash
DATE=$(date +%Y-%m-%d)
mkdir -p reports/dependency_licenses/$DATE
pipdeptree -p masonq --json > reports/dependency_licenses/$DATE/masonq_tree.json
pip-licenses --format=csv --with-authors --with-urls --with-license-file --no-license-path \
    > reports/dependency_licenses/$DATE/licenses_full.csv
# (subsequent filter + attribution bundling — see scripts/scan_dependencies.sh)
```
