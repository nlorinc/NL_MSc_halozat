"""
Affiliációs ID-k és intézményi blokkok feldolgozásához használt segédfüggvények.
"""

from __future__ import annotations

import re
import unicodedata
import numpy as np
import pandas as pd
import pycountry

from .parse_utils import split_scopus_multivalue, normalize_text_token


def strip_accents(text: str) -> str:
    """
    Ékezetek eltávolítása.
    """
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def normalize_match_text(value) -> str | float:
    """
    Szöveg normalizálása összehasonlításhoz:
    - kisbetűsítés
    - ékezetek eltávolítása
    - írásjelek eltávolítása
    - szóközök összevonása
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = strip_accents(str(text).lower())
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if text == "":
        return np.nan

    return text


def normalize_affil_id(value) -> str | float:
    """
    Affiliációs ID tisztítása sztringgé.
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = str(text).strip()
    text = re.sub(r"\.0$", "", text)

    if text in {"", "-", "--", "---"}:
        return np.nan

    return text


def pair_affiliation_ids_and_names(affil_ids_value, affil_names_value) -> tuple[list[dict], bool]:
    """
    A Scopus Affiliation IDs és Scopus Affiliation names mezők párosítása.
    """
    affil_ids = [normalize_affil_id(x) for x in split_scopus_multivalue(affil_ids_value)]
    affil_names = [normalize_text_token(x) for x in split_scopus_multivalue(affil_names_value)]

    n_ids = len(affil_ids)
    n_names = len(affil_names)
    n = max(n_ids, n_names)

    pairs = []

    for i in range(n):
        affil_id_i = affil_ids[i] if i < n_ids else np.nan
        affil_name_i = affil_names[i] if i < n_names else np.nan

        if pd.isna(affil_id_i) and pd.isna(affil_name_i):
            continue

        pairs.append({
            "affil_position": i + 1,
            "affil_id": affil_id_i,
            "affil_name_raw": affil_name_i,
        })

    lengths_match = (n_ids == n_names)

    return pairs, lengths_match


def build_kar_name_lookup(kar_map: dict) -> pd.DataFrame:
    """
    Kari név-lookup a fájlnévbeli kulcsokból.
    """
    rows = []

    for kar_name_key, kar_code in kar_map.items():
        kar_name_guess = kar_name_key.replace("_", " ")
        rows.append({
            "kar_code": kar_code,
            "kar_name_key": kar_name_key,
            "kar_name_guess": kar_name_guess,
            "kar_name_norm": normalize_match_text(kar_name_guess),
        })

    return pd.DataFrame(rows).sort_values("kar_code", kind="stable").reset_index(drop=True)


def build_publication_affiliation_occurrence(
    df_raw_keyed: pd.DataFrame,
    pub_id_col: str = "pub_id",
    affil_ids_col: str = "Scopus Affiliation IDs",
    affil_names_col: str = "Scopus Affiliation names",
    source_kar_col: str = "source_kar",
    source_file_col: str = "source_file",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A nyers, már pub_id-val ellátott kari rekordokból létrehozza
    az affiliáció-előfordulás táblát.

    1 sor = 1 affiliáció 1 publikációban 1 kari kontextusban
    """
    rows = []

    n_input_rows = 0
    n_length_mismatch_rows = 0

    for _, row in df_raw_keyed.iterrows():
        n_input_rows += 1

        pub_id = row[pub_id_col]
        affil_ids_value = row[affil_ids_col]
        affil_names_value = row[affil_names_col]
        source_kar = row[source_kar_col] if source_kar_col in df_raw_keyed.columns else np.nan
        source_file = row[source_file_col] if source_file_col in df_raw_keyed.columns else np.nan

        pairs, lengths_match = pair_affiliation_ids_and_names(affil_ids_value, affil_names_value)

        if not lengths_match:
            n_length_mismatch_rows += 1

        for item in pairs:
            rows.append({
                "pub_id": pub_id,
                "source_kar": source_kar,
                "source_file": source_file,
                "affil_position": item["affil_position"],
                "affil_id": item["affil_id"],
                "affil_name_raw": item["affil_name_raw"],
            })

    out = pd.DataFrame(rows)

    if not out.empty:
        out = out.drop_duplicates(
            subset=["pub_id", "source_kar", "affil_position", "affil_id", "affil_name_raw"],
            keep="first"
        ).reset_index(drop=True)

        out = out.sort_values(
            ["pub_id", "source_kar", "affil_position"],
            kind="stable"
        ).reset_index(drop=True)

    audit = pd.Series({
        "n_input_rows": n_input_rows,
        "n_affiliation_occurrence_rows": len(out),
        "n_unique_publications": int(out["pub_id"].nunique()) if not out.empty else 0,
        "n_unique_affil_ids": int(out["affil_id"].nunique(dropna=True)) if not out.empty else 0,
        "n_length_mismatch_rows": n_length_mismatch_rows,
    })

    return out, audit


def _most_frequent_nonnull(series: pd.Series):
    values = (
        series.dropna()
        .astype(str)
        .str.strip()
    )
    values = values[values != ""]

    if values.empty:
        return np.nan

    return values.value_counts().idxmax()


def build_de_affiliation_dict(
    publication_affiliation_occurrence: pd.DataFrame,
    de_central_affil_id: str = "60004400",
    source_kar_col: str = "source_kar",
    affil_id_col: str = "affil_id",
    affil_name_col: str = "affil_name_raw",
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    A nyers affiliáció-előfordulásokból felépíti a DE kari affiliációs szótárat
    coverage-alapú logikával.

    A kiválasztás logikája:
    - minden kari Excel biztosan az adott karhoz tartozó publikációkat tartalmazza
    - ezért karonként azt az affiliációs ID-t választjuk, amely a legtöbb
      kari publikációban előfordul
    - a DE központi affiliációs ID-t (pl. 60004400) kizárjuk
    """
    work = publication_affiliation_occurrence.copy()

    work = work.loc[
        work[source_kar_col].notna() &
        work[affil_id_col].notna()
    ].copy()

    work[affil_id_col] = work[affil_id_col].astype(str).str.strip()
    de_central_affil_id = str(de_central_affil_id).strip()

    # Kizárjuk a DE központi affiliációs ID-t
    work = work.loc[
        work[affil_id_col] != de_central_affil_id
    ].copy()

    # Karonként összes publikációszám
    kar_pub_totals = (
        work[[source_kar_col, "pub_id"]]
        .drop_duplicates()
        .groupby(source_kar_col)["pub_id"]
        .nunique()
        .reset_index(name="n_publications_total_for_kar")
    )

    # Karonként és affiliációs ID-nként: hány publikációban fordul elő
    candidate_map = (
        work.groupby([source_kar_col, affil_id_col], dropna=False)
        .agg(
            n_publications_with_affil=("pub_id", "nunique"),
            affil_name_raw=(affil_name_col, _most_frequent_nonnull),
        )
        .reset_index()
        .rename(columns={
            source_kar_col: "kar_code",
            affil_id_col: "affil_id",
        })
    )

    candidate_map = candidate_map.merge(
        kar_pub_totals.rename(columns={source_kar_col: "kar_code"}),
        on="kar_code",
        how="left"
    )

    candidate_map["coverage"] = (
        candidate_map["n_publications_with_affil"] /
        candidate_map["n_publications_total_for_kar"]
    )

    candidate_map = candidate_map.sort_values(
        ["kar_code", "coverage", "n_publications_with_affil", "affil_id"],
        ascending=[True, False, False, True],
        kind="stable"
    ).reset_index(drop=True)

    candidate_map["rank_within_kar"] = (
        candidate_map.groupby("kar_code").cumcount() + 1
    )

    best_cov = candidate_map.groupby("kar_code")["coverage"].transform("max")
    candidate_map["coverage_gap_to_best"] = best_cov - candidate_map["coverage"]

    de_affiliation_candidates = candidate_map.copy()

    # Karonként a legnagyobb lefedettségű affiliációs ID lesz a kiválasztott
    de_affiliation_dict = (
        de_affiliation_candidates
        .loc[de_affiliation_candidates["rank_within_kar"] == 1]
        .copy()
        [["affil_id", "affil_name_raw", "kar_code", "n_publications_with_affil",
          "n_publications_total_for_kar", "coverage"]]
        .sort_values(["kar_code", "affil_id"], kind="stable")
        .reset_index(drop=True)
    )

    # Diagnosztikai célra: karonként a top 3 jelölt
    de_affiliation_candidates_top3 = (
        de_affiliation_candidates
        .loc[de_affiliation_candidates["rank_within_kar"] <= 3]
        .copy()
        .sort_values(["kar_code", "rank_within_kar"], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_affiliation_occurrence_rows": len(publication_affiliation_occurrence),
        "n_candidate_rows": len(de_affiliation_candidates),
        "n_unique_de_affil_ids": int(de_affiliation_dict["affil_id"].nunique()) if not de_affiliation_dict.empty else 0,
        "n_kars_covered": int(de_affiliation_dict["kar_code"].nunique()) if not de_affiliation_dict.empty else 0,
        "min_selected_coverage": float(de_affiliation_dict["coverage"].min()) if not de_affiliation_dict.empty else np.nan,
        "mean_selected_coverage": float(de_affiliation_dict["coverage"].mean()) if not de_affiliation_dict.empty else np.nan,
    })

    return de_affiliation_dict, audit, de_affiliation_candidates_top3

def contains_any_keyword(text: str | float, keywords: list[str]) -> bool:
    """
    Egyszerű kulcsszó-ellenőrzés normalizált szövegre.
    """
    if pd.isna(text):
        return False

    padded = f" {text} "
    return any(f" {kw} " in padded for kw in keywords)


def is_institution_like_affil_name(value) -> bool:
    """
    Heurisztika: az affiliáció neve intézményi szintűnek látszik-e.
    """
    text = normalize_match_text(value)

    institution_keywords = [
        "university", "egyetem", "universitat", "universite", "universidad",
        "universita", "academy", "hospital", "medical center", "medical centre",
        "center", "centre", "research center", "research centre",
        "institute", "institut", "college"
    ]

    return contains_any_keyword(text, institution_keywords)


def is_subunit_like_affil_name(value) -> bool:
    """
    Heurisztika: az affiliáció neve kari / tanszéki / al-egység jellegű-e.
    """
    text = normalize_match_text(value)

    subunit_keywords = [
        "faculty", "kar", "department", "dept", "school",
        "campus", "clinic", "klinika", "unit", "division"
    ]

    return contains_any_keyword(text, subunit_keywords)


def build_publication_external_root_occurrence(
    publication_affiliation_occurrence: pd.DataFrame,
    de_affiliation_dict: pd.DataFrame,
    de_central_affil_id: str = "60004400",
    pub_id_col: str = "pub_id",
    affil_pos_col: str = "affil_position",
    affil_id_col: str = "affil_id",
    affil_name_col: str = "affil_name_raw",
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Publikációnként megpróbálja kiválasztani a külső intézményi gyökér-ID-ket.

    Kimenet:
    - publication_external_root_occurrence:
        1 sor = 1 publikáció – 1 külső intézményi gyökérjelölt
    - audit
    - external_root_affil_stats
    """
    work = publication_affiliation_occurrence[
        [pub_id_col, affil_pos_col, affil_id_col, affil_name_col]
    ].drop_duplicates().copy()

    work = work.loc[work[affil_id_col].notna()].copy()
    work[affil_id_col] = work[affil_id_col].astype(str).str.strip()

    de_affil_ids = set(de_affiliation_dict["affil_id"].astype(str).tolist())
    de_affil_ids.add(str(de_central_affil_id).strip())

    work["is_de_affil"] = work[affil_id_col].isin(de_affil_ids)
    work["is_institution_like"] = work[affil_name_col].map(is_institution_like_affil_name)
    work["is_subunit_like"] = work[affil_name_col].map(is_subunit_like_affil_name)

    rows = []
    n_publications_with_external_affils = 0
    n_publications_with_selected_roots = 0
    n_fallback_rows = 0

    for pub_id, grp in work.groupby(pub_id_col, sort=False):
        grp = grp.sort_values(affil_pos_col, kind="stable").reset_index(drop=True)

        external_grp = grp.loc[~grp["is_de_affil"]].copy()

        if external_grp.empty:
            continue

        n_publications_with_external_affils += 1
        selected_root_ids = set()

        for i in range(len(grp)):
            current = grp.iloc[i]

            if current["is_de_affil"]:
                continue

            next_is_external_subunit = False
            if i + 1 < len(grp):
                nxt = grp.iloc[i + 1]
                next_is_external_subunit = (
                    (not nxt["is_de_affil"]) and bool(nxt["is_subunit_like"])
                )

            is_root_candidate = bool(current["is_institution_like"] or next_is_external_subunit)

            if is_root_candidate and current[affil_id_col] not in selected_root_ids:
                rows.append({
                    "pub_id": pub_id,
                    "root_affil_id": current[affil_id_col],
                    "root_affil_name_raw": current[affil_name_col],
                    "root_affil_position": current[affil_pos_col],
                    "selection_reason": "institution_like_or_parent_of_subunit",
                })
                selected_root_ids.add(current[affil_id_col])

        # Fallback: ha van külső affiliáció, de nem találtunk root-jelöltet,
        # akkor az első külső affiliációt megtartjuk
        if len(selected_root_ids) == 0:
            fallback = external_grp.iloc[0]
            rows.append({
                "pub_id": pub_id,
                "root_affil_id": fallback[affil_id_col],
                "root_affil_name_raw": fallback[affil_name_col],
                "root_affil_position": fallback[affil_pos_col],
                "selection_reason": "first_external_fallback",
            })
            selected_root_ids.add(fallback[affil_id_col])
            n_fallback_rows += 1

        if len(selected_root_ids) > 0:
            n_publications_with_selected_roots += 1

    publication_external_root_occurrence = pd.DataFrame(rows)

    if not publication_external_root_occurrence.empty:
        publication_external_root_occurrence = (
            publication_external_root_occurrence
            .drop_duplicates(subset=["pub_id", "root_affil_id"], keep="first")
            .sort_values(["pub_id", "root_affil_position"], kind="stable")
            .reset_index(drop=True)
        )

    external_root_affil_stats = (
        publication_external_root_occurrence
        .groupby(["root_affil_id", "root_affil_name_raw", "selection_reason"], dropna=False)
        .agg(
            n_publications=("pub_id", "nunique"),
        )
        .reset_index()
        .sort_values(["n_publications", "root_affil_name_raw"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_unique_publications_total": int(work[pub_id_col].nunique()) if not work.empty else 0,
        "n_publications_with_external_affils": n_publications_with_external_affils,
        "n_publications_with_selected_roots": n_publications_with_selected_roots,
        "n_root_occurrence_rows": len(publication_external_root_occurrence),
        "n_unique_root_affil_ids": int(
            publication_external_root_occurrence["root_affil_id"].nunique()
        ) if not publication_external_root_occurrence.empty else 0,
        "n_fallback_rows": n_fallback_rows,
    })

    return publication_external_root_occurrence, audit, external_root_affil_stats



COUNTRY_NAME_TO_ISO3 = {
    "Hungary": "HUN",
    "Mozambique": "MOZ",
    "Zambia": "ZMB",
    "Germany": "DEU",
    "France": "FRA",
    "United Kingdom": "GBR",
    "England": "GBR",
    "Scotland": "GBR",
    "Wales": "GBR",
    "United States": "USA",
    "United States of America": "USA",
    "USA": "USA",
    "Canada": "CAN",
    "Italy": "ITA",
    "Spain": "ESP",
    "Romania": "ROU",
    "Slovakia": "SVK",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Netherlands": "NLD",
    "Switzerland": "CHE",
    "Sweden": "SWE",
    "Norway": "NOR",
    "Denmark": "DNK",
    "Poland": "POL",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Serbia": "SRB",
    "Croatia": "HRV",
    "Slovenia": "SVN",
    "Finland": "FIN",
    "Ireland": "IRL",
    "Australia": "AUS",
    "China": "CHN",
    "Japan": "JPN",
    "South Korea": "KOR",
    "Korea": "KOR",
    "India": "IND",
    "Israel": "ISR",
    "Turkey": "TUR",
    "Iran": "IRN",
    "Saudi Arabia": "SAU",
    "Pakistan": "PAK",
    "Sri Lanka": "LKA",
    "Yemen": "YEM",
    "Peru": "PER",
    "Kyrgyzstan": "KGZ",
    "Dominican Republic": "DOM",
    "Congo": "COG",
    "Bolivia": "BOL",
    "Seychelles": "SYC",
    "Mongolia": "MNG",
    "Puerto Rico": "PRI",
    "Brunei Darussalam": "BRN",
    "Namibia": "NAM",
    "Bhutan": "BTN",
    "Somalia": "SOM",
    "Papua New Guinea": "PNG",
    "Niger": "NER",
    "Myanmar": "MMR",
    "Martinique": "MTQ",
    "Cuba": "CUB",
    "Grenada": "GRD",
    "Senegal": "SEN",
    "Burkina Faso": "BFA",
    "Monaco": "MCO",
    "New Caledonia": "NCL",
    "Afghanistan": "AFG",
    "Gabon": "GAB",
    "Malawi": "MWI",
    "Egypt": "EGY",
    "Montenegro": "MNE",
    "South Africa": "ZAF",
    "Iraq": "IRQ",
    "Greece": "GRC",
    "Portugal": "PRT",
    "Mexico": "MEX",
    "United Arab Emirates": "ARE",
    "Ukraine": "UKR",
    "Russian Federation": "RUS",
    "Lithuania": "LTU",
    "Indonesia": "IDN",
    "Brazil": "BRA",
    "Bangladesh": "BGD",
    "Lebanon": "LBN",
    "Taiwan": "TWN",
    "Jordan": "JOR",
    "Ethiopia": "ETH",
    "Viet Nam": "VNM",
    "Bulgaria": "BGR",
    "Chile": "CHL",
    "Botswana": "BWA",
    "Qatar": "QAT",
    "Luxembourg": "LUX",
    "Nigeria": "NGA",
    "Singapore": "SGP",
    "Malaysia": "MYS",
    "Syrian Arab Republic": "SYR",
    "Ghana": "GHA",
    "Azerbaijan": "AZE",
    "Estonia": "EST",
    "Thailand": "THA",
    "Kenya": "KEN",
    "Cyprus": "CYP",
    "Georgia": "GEO",
    "Argentina": "ARG",
    "Kuwait": "KWT",
    "Uruguay": "URY",
    "Kazakhstan": "KAZ",
    "Sudan": "SDN",
    "North Macedonia": "MKD",
    "Uganda": "UGA",
    "New Zealand": "NZL",
    "Latvia": "LVA",
    "Iceland": "ISL",
    "Palestine": "PSE",
    "Venezuela": "VEN",
    "Ecuador": "ECU",
    "Albania": "ALB",
    "Colombia": "COL",
    "Hong Kong": "HKG",
    "Uzbekistan": "UZB",
    "Bosnia and Herzegovina": "BIH",
    "Tunisia": "TUN",
    "Algeria": "DZA",
    "Panama": "PAN",
    "Oman": "OMN",
    "Morocco": "MAR",
    "Philippines": "PHL",
    "Andorra": "AND",
    "Moldova": "MDA",
    "Armenia": "ARM",
    "Malta": "MLT",
    "Angola": "AGO",
    "Paraguay": "PRY",
    "Antigua and Barbuda": "ATG",
    "Benin": "BEN",
    "Belarus": "BLR",
    "Costa Rica": "CRI",
    "Nepal": "NPL",
    "Libya": "LBY",
    "Belize": "BLZ",
    "Democratic Republic Congo": "COD",
    "Guatemala": "GTM",
    "Saint Kitts and Nevis": "KNA",
    "Tanzania": "TZA",
    "Laos": "LAO",
    "Macao": "MAC",
    "Eritrea": "ERI",
    "Bahrain": "BHR",
    "Côte d'Ivoire": "CIV",
    "Cameroon": "CMR"
}


# 1. Meglévő, projekt-specifikus országnevek
COUNTRY_NAME_TO_ISO3_NORM = {
    normalize_match_text(k): v
    for k, v in COUNTRY_NAME_TO_ISO3.items()
}

# 2. Teljes ISO 3166-1 ország- és területlista
# Hivatalos és alternatív nevekkel
for country in pycountry.countries:
    for attr in ("name", "official_name", "common_name"):
        name = getattr(country, attr, None)

        if name:
            COUNTRY_NAME_TO_ISO3_NORM.setdefault(
                normalize_match_text(name),
                country.alpha_3
            )

# 3. További gyakori, nem hivatalos névváltozatok
COUNTRY_ALIASES = {
    "Ivory Coast": "CIV",
    "Trinidad & Tobago": "TTO",
    "UK": "GBR",
    "Great Britain": "GBR",
    "US": "USA",
    "Russia": "RUS",
    "Vietnam": "VNM",
    "Türkiye": "TUR",
    "DR Congo": "COD",
    "Congo (Kinshasa)": "COD",
    "Congo (Brazzaville)": "COG",
}

for name, iso3 in COUNTRY_ALIASES.items():
    COUNTRY_NAME_TO_ISO3_NORM[
        normalize_match_text(name)
    ] = iso3

# 4. ISO-kód -> országnév visszakeresés
ISO3_TO_COUNTRY = {}

for country_name, iso3 in COUNTRY_NAME_TO_ISO3.items():
    ISO3_TO_COUNTRY.setdefault(iso3, country_name)

for country in pycountry.countries:
    ISO3_TO_COUNTRY.setdefault(
        country.alpha_3,
        country.name
    )



def country_to_iso3(value) -> str | float:
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    norm = normalize_match_text(text)

    if pd.isna(norm):
        return np.nan

    return COUNTRY_NAME_TO_ISO3_NORM.get(norm, np.nan)


def split_country_region_list(value) -> list[str]:
    """
    Country/Region mező szétszedése.
    """
    parts = split_scopus_multivalue(value)
    parts = [normalize_text_token(x) for x in parts]
    parts = [x for x in parts if not pd.isna(x)]
    return parts


def build_publication_country_occurrence(
    df_raw_keyed: pd.DataFrame,
    pub_id_col: str = "pub_id",
    countries_col: str = "Country/Region",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A nyers publikációs rekordokból publikáció–ország kapcsolótáblát készít.
    1 sor = 1 publikáció – 1 ország
    """
    rows = []

    for _, row in df_raw_keyed[[pub_id_col, countries_col]].drop_duplicates().iterrows():
        pub_id = row[pub_id_col]
        countries = split_country_region_list(row[countries_col])

        for c in countries:
            rows.append({
                "pub_id": pub_id,
                "country": c,
                "country_code": country_to_iso3(c),
            })

    out = pd.DataFrame(rows)

    if not out.empty:
        out["_country_key"] = np.where(
            out["country_code"].notna(),
            out["country_code"],
            "UNKNOWN::" + out["country"].astype(str)
        )

        out = (
            out.drop_duplicates(subset=["pub_id", "_country_key"], keep="first")
            .drop(columns="_country_key")
            .sort_values(["pub_id", "country_code"], kind="stable")
            .reset_index(drop=True)
        )

    audit = pd.Series({
        "n_publication_country_rows": len(out),
        "n_unique_publications": int(out["pub_id"].nunique()) if not out.empty else 0,
        "n_unique_countries": int(out["country_code"].nunique(dropna=True)) if not out.empty else 0,
        "n_missing_country_code": int(out["country_code"].isna().sum()) if not out.empty else 0,

    })

    return out, audit


def build_publication_institution_link(
    publication_external_root_occurrence: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    A kiválasztott külső intézményi root affiliációkból létrehozza:
    - a publikáció–intézmény kapcsolótáblát
    - az intézményi szótárat
    - egy auditot

    Országot itt még nem rendelünk hozzá, az külön iteratív lépésben jön.
    """
    root = publication_external_root_occurrence.copy()

    if root.empty:
        publication_institution_link = pd.DataFrame(
            columns=["pub_id", "inst_id", "inst_name_canonical", "is_de"]
        )
        institution_dict = pd.DataFrame(
            columns=["inst_id", "inst_name_canonical", "is_de", "n_publications_with_de"]
        )
        audit = pd.Series({
            "n_publication_institution_rows": 0,
            "n_unique_institutions": 0,
        })
        return publication_institution_link, institution_dict, audit

    root = root.rename(columns={
        "root_affil_id": "inst_id",
        "root_affil_name_raw": "inst_name_canonical",
    }).copy()

    root["inst_id"] = root["inst_id"].astype(str).str.strip()
    root["is_de"] = False

    publication_institution_link = (
        root[["pub_id", "inst_id", "inst_name_canonical", "is_de"]]
        .drop_duplicates(subset=["pub_id", "inst_id"], keep="first")
        .sort_values(["pub_id", "inst_id"], kind="stable")
        .reset_index(drop=True)
    )

    institution_dict = (
        publication_institution_link
        .groupby(["inst_id", "inst_name_canonical", "is_de"], dropna=False)
        .agg(
            n_publications_with_de=("pub_id", "nunique"),
        )
        .reset_index()
        .sort_values(["n_publications_with_de", "inst_name_canonical"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_publication_institution_rows": len(publication_institution_link),
        "n_unique_institutions": int(institution_dict["inst_id"].nunique()),
    })

    return publication_institution_link, institution_dict, audit


def infer_institution_countries(
    publication_institution_link: pd.DataFrame,
    publication_country_occurrence: pd.DataFrame,
    accept_iterative_estimates: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Intézmény -> ország hozzárendelés konzervatív, iteratív szabályokkal.

    Szabályok:
    1. Egyországós publikációk: az ott szereplő külső intézmények biztosan ahhoz az országhoz tartoznak.
    2. Két- vagy többországós publikációk: csak akkor inferálunk, ha pontosan 1 feloldatlan
       külső intézmény van, és a nem-HUN országok között pontosan 1 még nem lefedett marad.
    """
    pil = publication_institution_link.copy()
    pco = publication_country_occurrence.copy()

    pub_to_countries = (
        pco.groupby("pub_id")["country_code"]
        .apply(lambda s: sorted(set(x for x in s.dropna())))
        .to_dict()
    )

    pub_to_insts = (
        pil.groupby("pub_id")["inst_id"]
        .apply(lambda s: sorted(set(x for x in s.dropna().astype(str))))
        .to_dict()
    )

    resolved = {}
    method = {}

    # 1. seed: egyországós publikációk
    for pub_id, countries in pub_to_countries.items():
        insts = pub_to_insts.get(pub_id, [])
        if len(countries) == 1 and len(insts) > 0:
            c = countries[0]
            for inst in insts:
                if inst not in resolved:
                    resolved[inst] = c
                    method[inst] = "single_country_publication"

    # 2. iteratív, csak nem-magyar országokra
    changed = True
    while changed:
        changed = False

        for pub_id, countries in pub_to_countries.items():
            insts = pub_to_insts.get(pub_id, [])
            if len(insts) == 0:
                continue

            unresolved = [i for i in insts if i not in resolved]
            if len(unresolved) != 1:
                continue

            non_hun_countries = {c for c in countries if c != "HUN"}
            known_non_hun = {
                resolved[i] for i in insts
                if i in resolved and resolved[i] != "HUN"
            }

            remaining_non_hun = non_hun_countries - known_non_hun

            if len(remaining_non_hun) == 1:
                inst = unresolved[0]
                c = list(remaining_non_hun)[0]

                if inst not in resolved:
                    resolved[inst] = c
                    method[inst] = "iterative_single_remaining_nonhun"
                    changed = True

    # Az iteratív országbesorolásokat jelöltként megőrizzük.
    candidate_resolved = resolved.copy()
    candidate_method = method.copy()

    # Alapértelmezésben csak az egyországos publikációk
    # alapján meghatározott országokat fogadjuk el.
    if not accept_iterative_estimates:
        resolved = {
            inst: code for inst, code in resolved.items()
            if method.get(inst) == "single_country_publication"
        }
        method = {
            inst: label for inst, label in method.items()
            if label == "single_country_publication"
        }
        # Konzervatív országbecslés:
        # legalább 5 publikáció, pontosan 1 közös külföldi ország

        unknown_country_pubs = set(
            pco.loc[pco["country_code"].isna(), "pub_id"].astype(str)
        )

        for inst_id, grp in pil.groupby("inst_id"):
            inst_id = str(inst_id)

            if inst_id in resolved:
                continue

            pubs = set(grp["pub_id"].dropna().astype(str))

            if len(pubs) < 5:
                continue

            if pubs & unknown_country_pubs:
                continue

            foreign_sets = [
                set(pub_to_countries.get(pub_id, [])) - {"HUN"}
                for pub_id in pubs
            ]

            if not all(foreign_sets):
                continue

            common = set.intersection(*foreign_sets)

            if len(common) == 1:
                resolved[inst_id] = next(iter(common))
                method[inst_id] = "common_foreign_country_min5"

    institution_country_dict = pil[["inst_id", "inst_name_canonical"]].drop_duplicates().copy()
    institution_country_dict["inst_id"] = institution_country_dict["inst_id"].astype(str)

    institution_country_dict["country_code_candidate"] = (
        institution_country_dict["inst_id"].map(candidate_resolved)
    )
    institution_country_dict["country_assignment_candidate_method"] = (
        institution_country_dict["inst_id"].map(candidate_method)
    )

    institution_country_dict["country_code"] = institution_country_dict["inst_id"].map(resolved)
    institution_country_dict["country"] = institution_country_dict["country_code"].map(ISO3_TO_COUNTRY)
    institution_country_dict["country_assignment_method"] = institution_country_dict["inst_id"].map(method)

    institution_country_dict["is_hungary"] = (
        institution_country_dict["country_code"]
        .map(lambda x: pd.NA if pd.isna(x) else x == "HUN")
        .astype("boolean")
    )
    institution_country_dict["is_resolved"] = institution_country_dict["country_code"].notna()

    publication_institution_link_enriched = pil.merge(
        institution_country_dict[
            ["inst_id", "country", "country_code", "is_hungary", "country_assignment_method", "is_resolved"]
        ],
        on="inst_id",
        how="left"
    )

    institution_dict_enriched = (
        institution_country_dict.merge(
            pil.groupby("inst_id")["pub_id"].nunique().reset_index(name="n_publications_with_de"),
            on="inst_id",
            how="left"
        )
        .sort_values(["n_publications_with_de", "inst_name_canonical"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_unique_institutions": int(institution_country_dict["inst_id"].nunique()),
        "n_resolved_institutions": int(institution_country_dict["is_resolved"].sum()),
        "n_unresolved_institutions": int((~institution_country_dict["is_resolved"]).sum()),
        "n_hungarian_institutions": int(institution_country_dict["is_hungary"].sum()),
        "n_nonhungarian_institutions": int(
            institution_country_dict["country_code"].notna().sum() - institution_country_dict["is_hungary"].sum()
        ),
        "n_single_country_seeded": int((institution_country_dict["country_assignment_method"] == "single_country_publication").sum()),
                "n_iterative_resolved": int(
            (institution_country_dict["country_assignment_method"] == "iterative_single_remaining_nonhun").sum()
        ),
                "n_unverified_iterative_candidates": int(
            (institution_country_dict["country_assignment_candidate_method"]
             == "iterative_single_remaining_nonhun").sum()
        ),
        "n_common_foreign_country_min5": int(
            (institution_country_dict["country_assignment_method"]
             == "common_foreign_country_min5").sum()
        ),
    })

    return (
        publication_institution_link_enriched,
        institution_dict_enriched,
        institution_country_dict,
        audit,
    )