"""Local publication gate for the DE network MSc repository.

Run from the project root: python prepublish_check.py
Uses only the Python standard library. Does not upload files or alter the project.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "NL_MSc_halozat_GitHub.ipynb"
MODULES = (
    "io_utils.py", "parse_utils.py", "affiliation_utils.py",
    "author_merge_utils.py", "network_utils.py", "analysis_utils.py",
)
errors: list[str] = []
warnings: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("[OK] " if condition else "[HIBA] ") + message)
    if not condition:
        errors.append(message)


def warn(message: str) -> None:
    print("[FIGYELEM] " + message)
    warnings.append(message)


def csv_records(path: Path, *, isolate_column: str | None = None):
    if not path.is_file():
        warn(f"Nincs meg a helyi kimenet: {path.relative_to(ROOT)}")
        return None, None
    count = 0
    extras = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        headers = reader.fieldnames or []
        if isolate_column and isolate_column not in headers:
            warn(f"Hiányzik a '{isolate_column}' oszlop: {path.relative_to(ROOT)}")
        for row in reader:
            count += 1
            if isolate_column and isolate_column in headers:
                try:
                    extras += float(row.get(isolate_column, "nan")) == 0
                except (ValueError, TypeError):
                    pass
    return count, (extras if isolate_column else None)


print("\n=== Fájlok és notebook ===")
for name in ("requirements.txt", "README.md", ".gitignore"):
    check((ROOT / name).is_file(), f"Megvan: {name}")
for name in MODULES:
    p = ROOT / "utils" / name
    check(p.is_file(), f"Megvan: utils/{name}")
    if p.is_file():
        try:
            ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
        except SyntaxError as e:
            check(False, f"Modul szintaktikai hibája: {name}: {e}")
check(NOTEBOOK.is_file(), f"Megvan: {NOTEBOOK.name}")
if NOTEBOOK.is_file():
    try:
        nb = json.loads(NOTEBOOK.read_text(encoding="utf-8-sig"))
        cells = nb.get("cells", [])
        code = [c for c in cells if c.get("cell_type") == "code"]
        check(nb.get("nbformat") == 4, "Notebook JSON-formátum (nbformat=4)")
        check(all(not c.get("outputs") and c.get("execution_count") is None for c in code),
              "A publikált notebook nem tartalmaz mentett futtatási kimenetet")
        version = str(nb.get("metadata", {}).get("language_info", {}).get("version", ""))
        if version != "3.14.0":
            warn(f"A notebook Python-verzió metaadata: {version or '(hiányzik)'}; referencia: 3.14.0")
        for i, c in enumerate(code):
            src = "".join(c.get("source", []))
            try:
                ast.parse(src)
            except SyntaxError as e:
                check(False, f"Notebook kódcella szintaktikai hibája: {i}: {e}")
                break
        else:
            print(f"[OK] {len(code)} Python-kódcella szintaxisa megfelelő")
        # Specific known issue: the figure-25 graph must include isolated authors.
        chapter25 = ""
        in_ch25 = False
        for c in cells:
            src = "".join(c.get("source", []))
            if c.get("cell_type") == "markdown" and src.lstrip().startswith("# 25."):
                in_ch25 = True
            elif c.get("cell_type") == "markdown" and src.lstrip().startswith("# 26."):
                in_ch25 = False
            if in_ch25 and c.get("cell_type") == "code":
                chapter25 += "\n" + src
        if "G = nx.Graph()" in chapter25 and not re.search(r"\bG\.add_nodes_from\s*\(", chapter25):
            check(False, "A 25. fejezet gráfjába nem kerülnek be az izolált szerzők (G.add_nodes_from hiányzik)")
        elif chapter25:
            print("[OK] A 25. fejezetben nem látszik az ismert kizárólag élalapú gráfépítési hiba")
        else:
            warn("A 25. fejezetet nem sikerült automatikusan azonosítani; manuális ellenőrzés szükséges")
    except (json.JSONDecodeError, UnicodeError) as e:
        check(False, f"A notebook nem olvasható: {e}")

print("\n=== Helyi referenciaeredmények (nem kerülnek feltöltésre) ===")
outputs = [
    ("Publikációk", "data_out/processed/publication_master.csv", 8223, None),
    ("Szerzői entitások", "data_out/processed/author_entity.csv", 7288, None),
    ("Társszerzői élek", "data_out/export/author_edges_export.csv", 40176, None),
    ("Partnerintézmények", "data_out/processed/institution_dict.csv", 5180, None),
    ("Külföldi országok/területek", "data_out/processed/de_country_edges.csv", 145, None),
    ("Szerzői izolált csomópontok", "data_out/processed/author_nodes_export_enriched.csv", 2561, "author_degree"),
]
for label, rel, expected, special in outputs:
    count, extra = csv_records(ROOT / rel, isolate_column=special)
    actual = extra if special else count
    if actual is not None:
        check(actual == expected, f"{label}: {actual} (referencia: {expected})")

figdir = ROOT / "data_out/processed/figures/ch25_meta"
if figdir.is_dir():
    n_png = len(list(figdir.glob("fig_25_*.png")))
    n_svg = len(list(figdir.glob("fig_25_*.svg")))
    check(n_png >= 11 and n_svg >= 11,
          f"25. fejezet ábrái: {n_png} PNG és {n_svg} SVG (legalább 11-11)")
else:
    warn("A 25. fejezet ábrakönyvtára nem található")

print("\n=== Git-adatvédelmi vizsgálat ===")
git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                     capture_output=True, text=True, check=False)
if git.returncode != 0:
    warn("Még nincs Git-repozitórium a gyökérben. A követett fájlokat commit előtt ellenőrizni kell")
else:
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=False).stdout.decode("utf-8", errors="replace").split("\x00")
    unsafe = []
    for path in filter(None, tracked):
        norm = path.replace("\\", "/")
        lower = norm.lower()
        if lower.startswith(("source_data/", "data_out/", ".venv/", "figures/")):
            unsafe.append(norm)
        elif lower.endswith((".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".feather", ".gephi", ".gexf")):
            unsafe.append(norm)
        elif lower.endswith(".ipynb") and norm != NOTEBOOK.name:
            unsafe.append(norm)
    check(not unsafe, "Git nem követ tiltott nyers adatot, kimenetet vagy másik notebookot")
    if unsafe:
        print("  Gyanús követett fájlok (max. 30):", *unsafe[:30], sep="\n  - ")

print("\n=== Összegzés ===")
print(f"Hibák: {len(errors)}; figyelmeztetések: {len(warnings)}")
print("Publikálási előellenőrzés:", "SIKERES" if not errors else "NEM SIKERES")
if errors:
    sys.exit(1)
