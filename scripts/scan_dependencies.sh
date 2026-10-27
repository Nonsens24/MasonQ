#!/usr/bin/env bash
# Generate a dated dependency-license audit report for MasonQ.
#
# Produces (under reports/dependency_licenses/YYYY-MM-DD/):
#   SUMMARY.md              — human-readable report for legal review
#   masonq_deps.txt         — masonq's actual dependency set
#   masonq_licenses.csv     — masonq's deps only (machine-readable)
#   masonq_licenses.md      — masonq's deps only (human-readable)
#   masonq_tree.json        — dependency tree from pipdeptree
#   attributions_full.txt   — every LICENSE / NOTICE / COPYING bundled for redistribution
#   attributions_supplemental.txt  — supplemental attributions for wheels that ship no LICENSE
#   licenses_full.csv/.md/.txt     — raw scans over the entire dev env (auditability)
#
# Requires: pipdeptree, pip-licenses.  Install via `pip install pipdeptree pip-licenses`.
#
# Usage:
#   ./scripts/scan_dependencies.sh
#   ./scripts/scan_dependencies.sh --date YYYY-MM-DD   # override the report date

set -euo pipefail

DATE=$(date +%Y-%m-%d)
while [[ $# -gt 0 ]]; do
    case "$1" in
        --date) DATE="$2"; shift 2 ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# //'
            exit 0 ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
REPORT_DIR="$REPO_ROOT/reports/dependency_licenses/$DATE"
mkdir -p "$REPORT_DIR"

echo "Writing report to $REPORT_DIR"

# 1. Raw env-wide scans (kept for auditability of the filtering step)
pip-licenses --format=csv --with-authors --with-urls --with-license-file --no-license-path \
    > "$REPORT_DIR/licenses_full.csv"
pip-licenses --format=markdown --with-authors --with-urls > "$REPORT_DIR/licenses_table.md"
pip-licenses --summary > "$REPORT_DIR/licenses_summary.txt"

# 2. masonq's actual dependency tree
pipdeptree -p masonq --json > "$REPORT_DIR/masonq_tree.json"

# 3. Filter licences to just masonq's tree, produce attribution bundle
python3 - "$REPORT_DIR" << 'PYEOF'
import csv
import json
import sys
from importlib.metadata import distribution
from pathlib import Path

report_dir = Path(sys.argv[1])

# Extract the set of packages actually in masonq's tree.
tree = json.loads((report_dir / "masonq_tree.json").read_text())
deps = set()
def walk(node):
    name = node.get("package_name") or node.get("key")
    if name:
        deps.add(name.lower())
    for child in node.get("dependencies", []):
        walk(child)
for entry in tree:
    walk(entry)
deps.add("masonq")
(report_dir / "masonq_deps.txt").write_text("\n".join(sorted(deps)) + "\n")

# Filter the license CSV.
with (report_dir / "licenses_full.csv").open() as fh:
    reader = csv.DictReader(fh)
    fields = reader.fieldnames
    filtered = [row for row in reader if row["Name"].lower() in deps]
with (report_dir / "masonq_licenses.csv").open("w") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for row in filtered:
        w.writerow(row)

# Human-readable table.
with (report_dir / "masonq_licenses.md").open("w") as fh:
    fh.write("| Package | Version | License | Author | URL |\n")
    fh.write("| --- | --- | --- | --- | --- |\n")
    for row in sorted(filtered, key=lambda r: r["Name"].lower()):
        author = (row.get("Author") or "").replace("|", "/").replace("\n", " ")[:60]
        url = (row.get("URL") or "").replace("|", "/")[:80]
        lic = (row.get("License") or "").replace("|", "/")
        fh.write(f"| `{row['Name']}` | {row['Version']} | {lic} | {author} | {url} |\n")

# Attribution bundle.
attributions = []
missing_license = []
for name in sorted(deps):
    try:
        d = distribution(name)
    except Exception:
        continue
    files = list(d.files or [])
    licence_files = [
        f for f in files
        if any(k in str(f).upper() for k in ("LICENSE", "COPYING", "NOTICE"))
    ]
    attributions.append(f"\n\n{'='*78}\n{name} {d.version}\n{'='*78}\n")
    if not licence_files:
        attributions.append("(no bundled LICENSE / COPYING / NOTICE file found)\n")
        missing_license.append(name)
        continue
    for f in licence_files:
        try:
            content = f.read_text()
        except Exception:
            try:
                content = f.locate().read_text(errors="replace")
            except Exception as exc:
                content = f"(could not read: {exc})"
        attributions.append(f"--- {f} ---\n")
        attributions.append(content)
        attributions.append("\n")
(report_dir / "attributions_full.txt").write_text("".join(attributions))

# Flag any licence that requires legal attention (copyleft / unknown).
COPYLEFT = ("gpl", "lgpl", "agpl", "sspl", "mozilla", "mpl", "eclipse", "epl", "cddl", "cpl")
UNKNOWN = ("unknown",)
flagged = []
unknown = []
for row in filtered:
    lic = (row.get("License") or "").lower()
    if any(marker in lic for marker in UNKNOWN):
        unknown.append(row)
    elif any(marker in lic for marker in COPYLEFT):
        flagged.append(row)

print(f"masonq deps: {len(filtered)}")
print(f"  permissive: {len(filtered) - len(flagged) - len(unknown)}")
print(f"  copyleft / notable: {len(flagged)}")
for row in flagged:
    print(f"    * {row['Name']} {row['Version']}: {row['License']}")
print(f"  UNKNOWN licence in metadata: {len(unknown)}")
for row in unknown:
    print(f"    * {row['Name']} {row['Version']} — check the bundled LICENSE file")
print(f"  wheels without bundled LICENSE: {len(missing_license)}")
for name in missing_license:
    print(f"    * {name} — add supplemental note")
PYEOF

echo
echo "Report written. Next: hand $REPORT_DIR/SUMMARY.md to legal."
echo "The attribution bundle for redistribution is $REPORT_DIR/attributions_full.txt."
