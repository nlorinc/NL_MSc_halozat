"""
Beolvasási és aggregációs segédfüggvények.
"""

from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd

from .parse_utils import (
    normalize_doi_series,
    pair_authors_and_ids,
    normalize_eid

)


def ensure_directories(dir_list):
    """
    Létrehozza a megadott mappákat, ha még nem léteznek.
    """
    for folder in dir_list:
        Path(folder).mkdir(parents=True, exist_ok=True)


def kar_code_from_filename(xlsx_path: Path, kar_map: dict) -> str:
    """
    Kari kód meghatározása a fájlnévből.
    """
    stem = xlsx_path.stem
    stem = stem.replace("Publications_of_Debreceni_Egyetem_", "")
    stem = stem.replace("Publications_of_", "")
    stem = re.sub(r"_2015.*$", "", stem)

    return kar_map[stem]

def discover_project_inputs(source_dir: Path, source_kari_dir: Path) -> tuple[list[Path], list[Path]]:
    """
        A projekt bemeneti fájljainak felderítése.

        Visszaad:
        - kari publikációs fájlok listája
        - DE szerzőlista-jelöltek listája
        """
    kari_files = sorted([
        p for p in source_kari_dir.glob("Publications_of*.xlsx")
        if p.is_file()
    ])

    author_candidates = sorted([
        p for p in source_dir.glob("DE_confirmed_authors*.xlsx")
        if p.is_file()
    ])

    return kari_files, author_candidates



def trim_after_first_empty_row(df: pd.DataFrame) -> pd.DataFrame:
    """
    Az első teljesen üres sorig megtartja a táblát.
    Az üres sortól lefelé minden eldobásra kerül.
    """
    empty_mask = df.isna().all(axis=1)

    if empty_mask.any():
        first_empty_idx = empty_mask.idxmax()
        df = df.loc[:first_empty_idx - 1].copy()

    return df

def find_excel_header_row(
    xlsx_path: Path,
    required=("Title", "Authors", "Scopus Author Ids"),
    scan_rows: int = 60
) -> int:
    """
    Megkeresi azt a sort, amely a tényleges fejlécnek tekinthető.
    """
    tmp = pd.read_excel(xlsx_path, header=None, nrows=scan_rows)
    required_lower = [x.lower() for x in required]

    for i in range(len(tmp)):
        row_values = (
            tmp.iloc[i]
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )
        if all(any(req == cell for cell in row_values) for req in required_lower):
            return i

    raise ValueError(f"Nem található fejlécsor ebben a fájlban: {xlsx_path.name}")


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Oszlopnevek egyszerű egységesítése.
    """
    out = df.copy()
    out.columns = (
        out.columns.astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return out


def read_kari_excel(xlsx_path: Path, kar_map: dict) -> tuple[pd.DataFrame, dict]:
    """
    Egy kari Excel fájl beolvasása.

    Visszaad:
    - a beolvasott DataFrame-et
    - egy rövid audit dictionary-t
    """
    header_row = find_excel_header_row(xlsx_path)
    df = pd.read_excel(xlsx_path, header=header_row)
    df = clean_column_names(df)
    df = trim_after_first_empty_row(df)

    source_kar = kar_code_from_filename(xlsx_path, kar_map)

    df["source_kar"] = source_kar
    df["source_file"] = xlsx_path.name

    audit = {
        "source_file": xlsx_path.name,
        "source_kar": source_kar,
        "header_row": header_row,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "has_doi": "DOI" in df.columns,
        "has_eid": "EID" in df.columns,
        "has_title": "Title" in df.columns,
        "has_authors": "Authors" in df.columns,
        "has_author_ids": "Scopus Author Ids" in df.columns,
    }

    return df, audit


def first_valid(series: pd.Series):
    """
    Az első érdemi, nem üres értéket adja vissza.
    """
    for value in series:
        if pd.isna(value):
            continue

        if isinstance(value, str):
            value = value.strip()
            if value == "" or value.lower() in {"nan", "none", "null"}:
                continue

        return value

    return np.nan


def join_unique_sorted(series: pd.Series, sep: str = "| "):
    """
    Egy sorozat egyedi, nem üres elemeit rendezve összefűzi.
    """
    values = []
    for value in series.dropna():
        text = str(value).strip()
        if text == "" or text.lower() in {"nan", "none", "null"}:
            continue
        values.append(text)

    values = sorted(set(values))

    if not values:
        return np.nan

    return sep.join(values)


def audit_doi_column(df: pd.DataFrame, doi_col: str = "DOI") -> pd.Series:
    """
    DOI oszlop auditja a nyers táblán.
    """
    work = df.copy()
    work["doi_norm"] = normalize_doi_series(work[doi_col])

    return pd.Series({
        "n_rows": len(work),
        "n_missing_doi_raw": int(work[doi_col].isna().sum()),
        "n_missing_doi_norm": int(work["doi_norm"].isna().sum()),
        "n_unique_doi_norm": int(work["doi_norm"].nunique(dropna=True)),
        "n_duplicated_doi_rows": int(work["doi_norm"].duplicated(keep=False).sum()),
    })


def build_publication_master(
    df_raw: pd.DataFrame,
    eid_col: str = "EID",
    doi_col: str = "DOI",
    keep_cols: list[str] | None = None,
    source_kar_col: str = "source_kar",
    source_file_col: str = "source_file",
    pub_id_prefix: str = "PUB",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    EID-alapú deduplikált publikációs törzs létrehozása.

    Elsődleges kulcs:
    1. EID
    2. ha EID hiányzik, DOI
    3. ha egyik sincs, egyedi sorazonosító fallback
    """
    if keep_cols is None:
        keep_cols = []

    raw = df_raw.copy()

    if doi_col in raw.columns:
        raw["doi_norm"] = normalize_doi_series(raw[doi_col])
    else:
        raw["doi_norm"] = np.nan

    if eid_col in raw.columns:
        raw["eid_norm"] = raw[eid_col].map(normalize_eid)
    else:
        raw["eid_norm"] = np.nan

    raw["pub_key"] = np.where(
        raw["eid_norm"].notna(),
        "EID::" + raw["eid_norm"].astype(str),
        np.where(
            raw["doi_norm"].notna(),
            "DOI::" + raw["doi_norm"].astype(str),
            "ROW::" + raw.index.astype(str)
        )
    )

    grouped = raw.groupby(["pub_key"], dropna=False)

    agg_map = {}
    for col in keep_cols:
        if col in raw.columns:
            agg_map[col] = first_valid

    publication_master = grouped.agg(agg_map).reset_index()

    publication_master["n_source_rows"] = grouped.size().values

    if source_kar_col in raw.columns:
        publication_master["n_source_kars"] = grouped[source_kar_col].nunique().values
        publication_master["source_kars"] = grouped[source_kar_col].apply(join_unique_sorted).values
    else:
        publication_master["n_source_kars"] = np.nan
        publication_master["source_kars"] = np.nan

    if source_file_col in raw.columns:
        publication_master["n_source_files"] = grouped[source_file_col].nunique().values
        publication_master["source_files"] = grouped[source_file_col].apply(join_unique_sorted).values
    else:
        publication_master["n_source_files"] = np.nan
        publication_master["source_files"] = np.nan

    publication_master["match_key_type"] = publication_master["pub_key"].str.split("::").str[0]

    sort_cols = [col for col in ["Year", "eid_norm", "doi_norm", "Title"] if col in publication_master.columns]
    if sort_cols:
        publication_master = publication_master.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    else:
        publication_master = publication_master.reset_index(drop=True)

    publication_master["pub_id"] = [
        f"{pub_id_prefix}_{i:06d}" for i in range(1, len(publication_master) + 1)
    ]

    preferred_order = [
        "pub_id",
        "pub_key",
        "match_key_type",
        "eid_norm",
        "doi_norm",
        "EID",
        "DOI",
        "Title",
        "Year",
        "Citations",
        "Field-Weighted Citation Impact",
        "Number of Authors",
        "Number of Institutions",
        "Number of Countries/Regions",
        "n_source_rows",
        "n_source_kars",
        "n_source_files",
        "source_kars",
        "source_files",
    ]
    ordered_cols = [c for c in preferred_order if c in publication_master.columns]
    other_cols = [c for c in publication_master.columns if c not in ordered_cols]
    publication_master = publication_master[ordered_cols + other_cols]

    raw_to_pub = publication_master[["pub_key", "pub_id"]].copy()
    df_raw_keyed = raw.merge(raw_to_pub, on="pub_key", how="left")

    return publication_master, df_raw_keyed



def build_publication_faculty_link(
    df_raw_keyed: pd.DataFrame,
    pub_id_col: str = "pub_id",
    source_kar_col: str = "source_kar",
    source_file_col: str = "source_file",
) -> pd.DataFrame:
    """
    A nyers, már pub_id-val ellátott kari rekordokból létrehozza
    az egyedi publikáció–kar kapcsolótáblát.

    1 sor = 1 publikáció – 1 kar kapcsolat
    """
    keep_cols = [c for c in [pub_id_col, source_kar_col, source_file_col] if c in df_raw_keyed.columns]

    work = df_raw_keyed[keep_cols].copy()
    work = work.dropna(subset=[pub_id_col, source_kar_col])

    grouped = work.groupby([pub_id_col, source_kar_col], dropna=False)

    out = grouped.size().reset_index(name="n_source_rows_kar")

    if source_file_col in work.columns:
        source_files = grouped[source_file_col].apply(join_unique_sorted).reset_index(name="source_files")
        out = out.merge(source_files, on=[pub_id_col, source_kar_col], how="left")
    else:
        out["source_files"] = np.nan

    out = out.rename(columns={source_kar_col: "kar_code"})
    out["link_source"] = "faculty_excel"

    out = out.sort_values([pub_id_col, "kar_code"], kind="stable").reset_index(drop=True)

    return out


def build_faculty_dict(
    kar_map: dict,
    publication_faculty_link: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    A kari rövidítésekből és opcionálisan a publikáció–kar kapcsolatokból
    felépíti a kar-törzstáblát.
    """
    rows = []

    for kar_name_key, kar_code in kar_map.items():
        rows.append({
            "kar_code": kar_code,
            "kar_name_key": kar_name_key,
            "is_de_faculty": 1,
        })

    faculty_dict = pd.DataFrame(rows).sort_values("kar_code", kind="stable").reset_index(drop=True)

    if publication_faculty_link is not None and not publication_faculty_link.empty:
        pub_counts = (
            publication_faculty_link
            .groupby("kar_code")["pub_id"]
            .nunique()
            .reset_index(name="publication_count")
        )

        faculty_dict = faculty_dict.merge(pub_counts, on="kar_code", how="left")
        faculty_dict["publication_count"] = faculty_dict["publication_count"].fillna(0).astype(int)
    else:
        faculty_dict["publication_count"] = 0

    return faculty_dict


def find_author_header_row(
    xlsx_path: Path,
    required=("Name", "Scopus author ID"),
    scan_rows: int = 60
) -> int:
    """
    Megkeresi a DE szerzőlista tényleges fejlécsorát.
    Alapértelmezés szerint a 'Name' és a 'Scopus author ID' oszlopokat keresi.
    """
    tmp = pd.read_excel(xlsx_path, header=None, nrows=scan_rows)
    required_lower = [x.lower() for x in required]

    for i in range(len(tmp)):
        row_values = (
            tmp.iloc[i]
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )
        if all(any(req == cell for cell in row_values) for req in required_lower):
            return i

    raise ValueError(f"Nem található fejlécsor ebben a fájlban: {xlsx_path.name}")


def read_de_author_excel(xlsx_path: Path) -> tuple[pd.DataFrame, dict]:
    """
    A DE-s megerősített szerzőlista beolvasása.
    """
    header_row = find_author_header_row(xlsx_path)
    df = pd.read_excel(xlsx_path, header=header_row)
    df = clean_column_names(df)
    df = trim_after_first_empty_row(df)

    audit = {
        "source_file": xlsx_path.name,
        "header_row": header_row,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "has_name": "Name" in df.columns,
        "has_scopus_author_id": "Scopus author ID" in df.columns,
        "has_citations": "Citations" in df.columns,
        "has_cpp": "Citations per Publication" in df.columns,
        "has_fwci": "Field-Weighted Citation Impact" in df.columns,
        "has_hindex": "h-index" in df.columns,
    }

    return df, audit


def build_de_author_ref(df_author_raw: pd.DataFrame) -> pd.DataFrame:
    """
    A nyers DE szerzőlistából létrehozza a minimálisan szükséges
    szerző-referencia táblát.
    """
    col_map = {
        "Name": "ref_author_name",
        "Scopus author ID": "ref_scopus_id",
        "Citations": "citations",
        "Citations per Publication": "cit_per_pub",
        "Field-Weighted Citation Impact": "fwci",
        "h-index": "h_index",
        "Primary author affiliation*": "primary_affiliation",
        "Scholarly Output": "scholarly_output",
        "Most recent publication": "most_recent_publication",
        "Oldest publication (since 1996)": "oldest_publication_since_1996",
        "ORCID (linked to Scopus author profile)": "orcid",
    }

    keep_existing = [c for c in col_map if c in df_author_raw.columns]

    out = df_author_raw[keep_existing].copy()
    out = out.rename(columns=col_map)

    # alap szöveges tisztítás
    if "ref_author_name" in out.columns:
        out["ref_author_name"] = (
            out["ref_author_name"]
            .astype(str)
            .str.strip()
            .replace({"": np.nan, "nan": np.nan})
        )

    if "ref_scopus_id" in out.columns:
        out["ref_scopus_id"] = (
            out["ref_scopus_id"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .replace({"": np.nan, "nan": np.nan})
        )

    # Egész szám típusú mezők normalizálása
    int_like_cols = [
        "citations",
        "scholarly_output",
        "most_recent_publication",
        "oldest_publication_since_1996",
        "h_index",
    ]

    for col in int_like_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # Tört értékű mezők normalizálása
    float_like_cols = ["cit_per_pub", "fwci"]
    for col in float_like_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")


    # üres név vagy üres scopus id esetén eldobjuk a sort
    required_cols = [c for c in ["ref_author_name", "ref_scopus_id"] if c in out.columns]
    out = out.dropna(subset=required_cols).copy()

    # esetleges duplikátumok kiszűrése
    dedup_cols = [c for c in ["ref_author_name", "ref_scopus_id"] if c in out.columns]
    out = out.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)

    return out


def build_publication_author_occurrence(
    df_raw_keyed: pd.DataFrame,
    pub_id_col: str = "pub_id",
    authors_col: str = "Authors",
    author_ids_col: str = "Scopus Author Ids",
    source_kar_col: str = "source_kar",
    source_file_col: str = "source_file",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A nyers, már pub_id-val ellátott kari rekordokból létrehozza
    a szerző-előfordulás táblát.

    1 sor = 1 szerző 1 publikációban 1 kari kontextusban
    """
    rows = []

    n_input_rows = 0
    n_length_mismatch_rows = 0

    for _, row in df_raw_keyed.iterrows():
        n_input_rows += 1

        pub_id = row[pub_id_col]
        authors_value = row[authors_col]
        author_ids_value = row[author_ids_col]
        source_kar = row[source_kar_col] if source_kar_col in df_raw_keyed.columns else np.nan
        source_file = row[source_file_col] if source_file_col in df_raw_keyed.columns else np.nan

        pairs, lengths_match = pair_authors_and_ids(authors_value, author_ids_value)

        if not lengths_match:
            n_length_mismatch_rows += 1

        n_authors_listed = len(pairs)

        for item in pairs:
            rows.append({
                "pub_id": pub_id,
                "source_kar": source_kar,
                "source_file": source_file,
                "author_position": item["author_position"],
                "author_name_raw": item["author_name_raw"],
                "scopus_author_id": item["scopus_author_id"],
                "n_authors_listed": n_authors_listed,
            })

    out = pd.DataFrame(rows)

    if not out.empty:
        out = out.drop_duplicates(
            subset=[
                "pub_id",
                "source_kar",
                "author_position",
                "author_name_raw",
                "scopus_author_id",
            ],
            keep="first"
        ).reset_index(drop=True)

        out = out.sort_values(
            ["pub_id", "source_kar", "author_position"],
            kind="stable"
        ).reset_index(drop=True)

    audit = pd.Series({
        "n_input_rows": n_input_rows,
        "n_occurrence_rows": len(out),
        "n_unique_publications": int(out["pub_id"].nunique()) if not out.empty else 0,
        "n_unique_authors_raw": int(out["author_name_raw"].nunique(dropna=True)) if not out.empty else 0,
        "n_unique_scopus_ids": int(out["scopus_author_id"].nunique(dropna=True)) if not out.empty else 0,
        "n_length_mismatch_rows": n_length_mismatch_rows,
    })

    return out, audit