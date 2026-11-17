"""
Hálózatépítési és hálózati metrikaszámítási segédfüggvények.
"""

from __future__ import annotations

from itertools import combinations
import numpy as np
import pandas as pd
import networkx as nx


def build_author_author_edges(
    publication_author_entity_link: pd.DataFrame,
    pub_id_col: str = "pub_id",
    author_id_col: str = "author_id",
    author_position_col: str = "author_position_min",
    weight_mode: str = "inverse_n_minus_1",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    DE szerző–szerző együttműködési háló építése publikáció-alapon.

    Kimenetek:
    - author_author_pair_occurrence:
        1 sor = 1 publikáció – 1 szerzőpár
    - author_author_edges:
        aggregált él-tábla
    - audit

    Súlyozás:
    - inverse_n_minus_1:
        egy k DE-s szerzős publikáció minden párjára 1 / (k - 1) súly jut
        így a kétszerzős cikk súlya 1, a háromszerzősé 0.5, stb.
    """
    link = publication_author_entity_link.copy()

    keep_cols = [c for c in [pub_id_col, author_id_col, author_position_col] if c in link.columns]
    link = link[keep_cols].drop_duplicates().copy()

    rows = []
    n_publications_total = 0
    n_publications_with_pairs = 0

    for pub_id, grp in link.groupby(pub_id_col, sort=False):
        n_publications_total += 1

        grp_pub = (
            grp.sort_values(author_position_col, kind="stable")
            .drop_duplicates(subset=[author_id_col], keep="first")
            .copy()
        )

        author_ids = grp_pub[author_id_col].astype(str).tolist()
        n_authors = len(author_ids)

        if n_authors < 2:
            continue

        n_publications_with_pairs += 1

        if weight_mode == "inverse_n_minus_1":
            pair_weight = 1.0 / (n_authors - 1)
        else:
            raise ValueError(f"Ismeretlen weight_mode: {weight_mode}")

        for a, b in combinations(author_ids, 2):
            source, target = sorted([a, b])

            rows.append({
                "pub_id": pub_id,
                "source": source,
                "target": target,
                "n_de_authors_in_pub": n_authors,
                "pair_weight": pair_weight,
            })

    author_author_pair_occurrence = pd.DataFrame(rows)

    if not author_author_pair_occurrence.empty:
        author_author_edges = (
            author_author_pair_occurrence
            .groupby(["source", "target"], dropna=False)
            .agg(
                pub_count=("pub_id", "nunique"),
                weight=("pair_weight", "sum"),
                min_n_de_authors_in_joint_pubs=("n_de_authors_in_pub", "min"),
                max_n_de_authors_in_joint_pubs=("n_de_authors_in_pub", "max"),
            )
            .reset_index()
            .sort_values(["weight", "pub_count", "source", "target"], ascending=[False, False, True, True], kind="stable")
            .reset_index(drop=True)
        )
    else:
        author_author_edges = pd.DataFrame(columns=[
            "source", "target", "pub_count", "weight",
            "min_n_de_authors_in_joint_pubs", "max_n_de_authors_in_joint_pubs"
        ])

    audit = pd.Series({
        "n_publications_total": int(n_publications_total),
        "n_publications_with_pairs": int(n_publications_with_pairs),
        "n_pair_occurrence_rows": int(len(author_author_pair_occurrence)),
        "n_unique_edges": int(len(author_author_edges)),
        "mean_edge_weight": float(author_author_edges["weight"].mean()) if len(author_author_edges) > 0 else np.nan,
        "max_edge_weight": float(author_author_edges["weight"].max()) if len(author_author_edges) > 0 else np.nan,
    })

    return author_author_pair_occurrence, author_author_edges, audit

def build_author_nodes_export(
    author_entity: pd.DataFrame,
    publication_author_entity_link: pd.DataFrame,
    kar_codes: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A szerző-entitásokból és a publikáció–szerző kapcsolatokból
    létrehozza a végleges szerző node export alapját.

    Ebben a fejezetben még nem számolunk NetworkX-metrikákat,
    csak a stabil alap attribútumokat készítjük elő.
    """
    ent = author_entity.copy()
    link = publication_author_entity_link.copy()

    # Publikációszám author_id szinten
    pub_counts = (
        link.groupby("author_id")["pub_id"]
        .nunique()
        .reset_index(name="pub_count_total")
    )

    # Minimum author pozíció az összes DE-s publikációban
    min_author_pos = (
        link.groupby("author_id")["author_position_min"]
        .min()
        .reset_index(name="best_author_position")
    )

    nodes = ent.merge(pub_counts, on="author_id", how="left")
    nodes = nodes.merge(min_author_pos, on="author_id", how="left")

    nodes["pub_count_total"] = nodes["pub_count_total"].fillna(0).astype(int)

    if "best_author_position" in nodes.columns:
        nodes["best_author_position"] = pd.to_numeric(
            nodes["best_author_position"], errors="coerce"
        ).astype("Int64")

    # Gephi-kompatibilis alapmezők
    nodes["Id"] = nodes["author_id"]
    nodes["Label"] = nodes["canonical_name"]

    # Kari evidence oszlopok biztosítása
    for kar in kar_codes:
        if kar not in nodes.columns:
            nodes[kar] = 0

    # Alap flags / összesítések
    nodes["is_multi_scopus_entity"] = nodes["n_scopus_ids"].fillna(0).astype(int) > 1
    nodes["has_primary_kar"] = nodes["primary_kar"].notna()
    nodes["is_inter_primary_kar"] = nodes["primary_kar"].eq("INTER")

    preferred_order = [
        "Id",
        "Label",
        "author_id",
        "canonical_name",
        "primary_kar",
        "n_scopus_ids",
        "scopus_ids_joined",
        "pub_count_total",
        "total_evidence",
        "n_kars_with_evidence",
        "citations",
        "cit_per_pub",
        "fwci",
        "h_index",
        "scholarly_output",
        "most_recent_publication",
        "oldest_publication_since_1996",
        "primary_affiliation",
        "best_author_position",
        "is_multi_scopus_entity",
        "has_primary_kar",
        "is_inter_primary_kar",
    ] + [k for k in kar_codes if k in nodes.columns]

    existing_preferred = [c for c in preferred_order if c in nodes.columns]
    other_cols = [c for c in nodes.columns if c not in existing_preferred]

    author_nodes_export = nodes[existing_preferred + other_cols].copy()

    author_nodes_export = author_nodes_export.sort_values(
        ["pub_count_total", "total_evidence", "canonical_name"],
        ascending=[False, False, True],
        kind="stable"
    ).reset_index(drop=True)

    audit = pd.Series({
        "n_author_nodes": int(len(author_nodes_export)),
        "n_nodes_with_primary_kar": int(author_nodes_export["has_primary_kar"].sum()),
        "n_nodes_with_inter_primary_kar": int(author_nodes_export["is_inter_primary_kar"].sum()),
        "n_multi_scopus_entities": int(author_nodes_export["is_multi_scopus_entity"].sum()),
        "n_nodes_with_publications": int((author_nodes_export["pub_count_total"] > 0).sum()),
        "max_pub_count_total": int(author_nodes_export["pub_count_total"].max()) if len(author_nodes_export) > 0 else 0,
    })

    return author_nodes_export, audit

from math import comb


def build_faculty_faculty_edges(
    publication_faculty_link: pd.DataFrame,
    pub_id_col: str = "pub_id",
    kar_col: str = "kar_code",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Kar–kar együttműködési háló építése publikáció-alapon.

    Kimenetek:
    - faculty_faculty_pair_occurrence:
        1 sor = 1 publikáció – 1 karpár (vagy self-loop)
    - faculty_faculty_edges:
        aggregált él-tábla
    - audit

    Súlyok:
    - pub_count_raw:
        nyers közös publikációszám
    - weight_frac:
        k karos publikáció esetén minden karpár 1 / C(k,2) súlyt kap
    - weight_inv_n_minus_1:
        k karos publikáció esetén minden karpár 1 / (k-1) súlyt kap

    Self-loop:
    - ha egy publikáció pontosan 1 karhoz tartozik, abból self-loop keletkezik
      1.0 súllyal.
    """
    pfl = publication_faculty_link[[pub_id_col, kar_col]].drop_duplicates().copy()

    rows = []
    n_publications_total = 0
    n_publications_with_self_loop = 0
    n_publications_with_interfaculty_edge = 0

    for pub_id, grp in pfl.groupby(pub_id_col, sort=False):
        n_publications_total += 1

        kars = sorted(set(grp[kar_col].dropna().astype(str).tolist()))
        n_kars = len(kars)

        if n_kars == 0:
            continue

        if n_kars == 1:
            kar = kars[0]
            rows.append({
                "pub_id": pub_id,
                "source": kar,
                "target": kar,
                "is_self_loop": True,
                "n_kars_in_pub": 1,
                "pub_count_raw": 1,
                "weight_frac": 1.0,
                "weight_inv_n_minus_1": 1.0,
            })
            n_publications_with_self_loop += 1
            continue

        n_publications_with_interfaculty_edge += 1

        weight_frac = 1.0 / comb(n_kars, 2)
        weight_inv = 1.0 / (n_kars - 1)

        for a, b in combinations(kars, 2):
            source, target = sorted([a, b])

            rows.append({
                "pub_id": pub_id,
                "source": source,
                "target": target,
                "is_self_loop": False,
                "n_kars_in_pub": n_kars,
                "pub_count_raw": 1,
                "weight_frac": weight_frac,
                "weight_inv_n_minus_1": weight_inv,
            })

    faculty_faculty_pair_occurrence = pd.DataFrame(rows)

    if not faculty_faculty_pair_occurrence.empty:
        faculty_faculty_edges = (
            faculty_faculty_pair_occurrence
            .groupby(["source", "target", "is_self_loop"], dropna=False)
            .agg(
                pub_count_raw=("pub_count_raw", "sum"),
                weight_frac=("weight_frac", "sum"),
                weight_inv_n_minus_1=("weight_inv_n_minus_1", "sum"),
                min_n_kars_in_joint_pubs=("n_kars_in_pub", "min"),
                max_n_kars_in_joint_pubs=("n_kars_in_pub", "max"),
            )
            .reset_index()
            .sort_values(
                ["weight_frac", "pub_count_raw", "source", "target"],
                ascending=[False, False, True, True],
                kind="stable"
            )
            .reset_index(drop=True)
        )
    else:
        faculty_faculty_edges = pd.DataFrame(columns=[
            "source", "target", "is_self_loop", "pub_count_raw",
            "weight_frac", "weight_inv_n_minus_1",
            "min_n_kars_in_joint_pubs", "max_n_kars_in_joint_pubs"
        ])

    audit = pd.Series({
        "n_publications_total": int(n_publications_total),
        "n_publications_with_self_loop": int(n_publications_with_self_loop),
        "n_publications_with_interfaculty_edge": int(n_publications_with_interfaculty_edge),
        "n_pair_occurrence_rows": int(len(faculty_faculty_pair_occurrence)),
        "n_unique_edges_total": int(len(faculty_faculty_edges)),
        "n_unique_self_loops": int(faculty_faculty_edges["is_self_loop"].sum()) if not faculty_faculty_edges.empty else 0,
        "n_unique_interfaculty_edges": int((~faculty_faculty_edges["is_self_loop"]).sum()) if not faculty_faculty_edges.empty else 0,
    })

    return faculty_faculty_pair_occurrence, faculty_faculty_edges, audit


def build_faculty_nodes_export(
        faculty_dict: pd.DataFrame,
        author_kar_profile: pd.DataFrame,
        publication_faculty_link: pd.DataFrame,
        faculty_faculty_edges: pd.DataFrame,
        kar_codes: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A kar-törzsből és a kapcsolódó táblákból felépíti a végleges kari node export alapját.

    Ebben a fejezetben még nem számolunk NetworkX-metrikákat,
    csak az alap attribútumokat és a Gephi-kompatibilis mezőket készítjük elő.
    """
    fac = faculty_dict.copy()

    # Publikációszám karonként
    pub_counts = (
        publication_faculty_link
        .groupby("kar_code")["pub_id"]
        .nunique()
        .reset_index(name="pub_count_total")
    )

    # Szerzőszámok a szerző-kar profil alapján
    # only_primary_authors: primary_kar szerint kizárólag ide sorolt szerzők
    primary_author_counts = (
        author_kar_profile.loc[
            author_kar_profile["primary_kar"].notna() &
            (author_kar_profile["primary_kar"] != "INTER")
            ]
        .groupby("primary_kar")["ref_scopus_id"]
        .nunique()
        .reset_index(name="n_authors_primary_only")
        .rename(columns={"primary_kar": "kar_code"})
    )

    # all_with_evidence: akiknél az adott kar evidence > 0
    kar_author_rows = []
    for kar in kar_codes:
        if kar in author_kar_profile.columns:
            n_auth = int((author_kar_profile[kar] > 0).sum())
            kar_author_rows.append({
                "kar_code": kar,
                "n_authors_with_any_evidence": n_auth,
            })

    all_author_counts = pd.DataFrame(kar_author_rows)

    # Self-loop adatok a kari élhálóból
    self_loops = (
        faculty_faculty_edges.loc[faculty_faculty_edges["is_self_loop"]]
        [["source", "pub_count_raw", "weight_frac", "weight_inv_n_minus_1"]]
        .rename(columns={
            "source": "kar_code",
            "pub_count_raw": "self_loop_pub_count_raw",
            "weight_frac": "self_loop_weight_frac",
            "weight_inv_n_minus_1": "self_loop_weight_inv_n_minus_1",
        })
        .copy()
    )

    nodes = fac.merge(pub_counts, on="kar_code", how="left")
    nodes = nodes.merge(primary_author_counts, on="kar_code", how="left")
    nodes = nodes.merge(all_author_counts, on="kar_code", how="left")
    nodes = nodes.merge(self_loops, on="kar_code", how="left")

    # hiányok kitöltése
    int_like_cols = [
        "publication_count",
        "pub_count_total",
        "n_authors_primary_only",
        "n_authors_with_any_evidence",
        "self_loop_pub_count_raw",
    ]
    for col in int_like_cols:
        if col in nodes.columns:
            nodes[col] = pd.to_numeric(nodes[col], errors="coerce").fillna(0).astype(int)

    float_like_cols = [
        "self_loop_weight_frac",
        "self_loop_weight_inv_n_minus_1",
    ]
    for col in float_like_cols:
        if col in nodes.columns:
            nodes[col] = pd.to_numeric(nodes[col], errors="coerce").fillna(0.0)

    # Gephi-kompatibilis mezők
    nodes["Id"] = nodes["kar_code"]
    nodes["Label"] = nodes["kar_code"]

    preferred_order = [
        "Id",
        "Label",
        "kar_code",
        "kar_name_key",
        "is_de_faculty",
        "publication_count",
        "pub_count_total",
        "n_authors_primary_only",
        "n_authors_with_any_evidence",
        "self_loop_pub_count_raw",
        "self_loop_weight_frac",
        "self_loop_weight_inv_n_minus_1",
    ]

    existing_preferred = [c for c in preferred_order if c in nodes.columns]
    other_cols = [c for c in nodes.columns if c not in existing_preferred]

    faculty_nodes_export = nodes[existing_preferred + other_cols].copy()

    faculty_nodes_export = faculty_nodes_export.sort_values(
        ["pub_count_total", "kar_code"],
        ascending=[False, True],
        kind="stable"
    ).reset_index(drop=True)

    audit = pd.Series({
        "n_faculty_nodes": int(len(faculty_nodes_export)),
        "n_nodes_with_publications": int((faculty_nodes_export["pub_count_total"] > 0).sum()),
        "n_nodes_with_primary_authors": int((faculty_nodes_export["n_authors_primary_only"] > 0).sum()),
        "n_nodes_with_any_evidence_authors": int((faculty_nodes_export["n_authors_with_any_evidence"] > 0).sum()),
        "max_pub_count_total": int(faculty_nodes_export["pub_count_total"].max()) if len(
            faculty_nodes_export) > 0 else 0,
    })

    return faculty_nodes_export, audit

def build_de_institution_edges(
    publication_faculty_link: pd.DataFrame,
    publication_institution_link: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    DE ↔ külső intézményi kapcsolatok felépítése.

    Kimenetek:
    - publication_de_institution_occurrence:
        1 sor = 1 publikáció – 1 külső intézmény
    - de_institution_edges:
        aggregált teljes DE ↔ intézmény él-tábla
    - publication_faculty_institution_occurrence:
        1 sor = 1 publikáció – 1 kar – 1 külső intézmény
    - faculty_institution_edges:
        aggregált kar ↔ intézmény él-tábla
    - audit

    Súlyozás:
    - teljes DE ↔ intézmény nézet:
        egy m külső intézményes publikációban minden intézmény 1 / m súlyt kap
    - kar ↔ intézmény nézet:
        egy k karos és m külső intézményes publikációban minden kar-intézmény pár 1 / (k * m) súlyt kap
    """
    pfl = publication_faculty_link[["pub_id", "kar_code"]].drop_duplicates().copy()

    pil_keep = [
        c for c in [
            "pub_id",
            "inst_id",
            "inst_name_canonical",
            "country",
            "country_code",
            "is_hungary",
            "is_de",
            "country_assignment_method",
            "is_resolved",
        ]
        if c in publication_institution_link.columns
    ]
    pil = publication_institution_link[pil_keep].drop_duplicates().copy()

    # Publikációnként hány kar és hány külső intézmény van
    pub_kar_counts = (
        pfl.groupby("pub_id")["kar_code"]
        .nunique()
        .reset_index(name="n_kars_in_pub")
    )

    pub_inst_counts = (
        pil.groupby("pub_id")["inst_id"]
        .nunique()
        .reset_index(name="n_institutions_in_pub")
    )

    # ---- 1. teljes DE ↔ intézmény publikációszintű occurrence ----
    publication_de_institution_occurrence = pil.merge(
        pub_inst_counts,
        on="pub_id",
        how="left"
    )

    publication_de_institution_occurrence["weight_frac_de_inst"] = (
        1.0 / publication_de_institution_occurrence["n_institutions_in_pub"]
    )

    publication_de_institution_occurrence["source"] = "DE"
    publication_de_institution_occurrence["target"] = publication_de_institution_occurrence["inst_id"]

    # ---- 2. aggregált DE ↔ intézmény élek ----
    agg_cols_de = [
        "inst_id",
        "inst_name_canonical",
        "country",
        "country_code",
        "is_hungary",
    ]
    agg_cols_de = [c for c in agg_cols_de if c in publication_de_institution_occurrence.columns]

    de_institution_edges = (
        publication_de_institution_occurrence
        .groupby(agg_cols_de, dropna=False)
        .agg(
            pub_count_raw=("pub_id", "nunique"),
            weight_frac=("weight_frac_de_inst", "sum"),
            min_n_institutions_in_pub=("n_institutions_in_pub", "min"),
            max_n_institutions_in_pub=("n_institutions_in_pub", "max"),
        )
        .reset_index()
    )

    de_institution_edges["source"] = "DE"
    de_institution_edges["target"] = de_institution_edges["inst_id"]

    de_institution_edges = de_institution_edges.sort_values(
        ["weight_frac", "pub_count_raw", "inst_name_canonical"],
        ascending=[False, False, True],
        kind="stable"
    ).reset_index(drop=True)

    # ---- 3. publikációszintű kar ↔ intézmény occurrence ----
    publication_faculty_institution_occurrence = pfl.merge(
        pil,
        on="pub_id",
        how="inner"
    )

    publication_faculty_institution_occurrence = publication_faculty_institution_occurrence.merge(
        pub_kar_counts,
        on="pub_id",
        how="left"
    )

    publication_faculty_institution_occurrence = publication_faculty_institution_occurrence.merge(
        pub_inst_counts,
        on="pub_id",
        how="left"
    )

    publication_faculty_institution_occurrence["weight_frac_fac_inst"] = (
        1.0 / (
            publication_faculty_institution_occurrence["n_kars_in_pub"] *
            publication_faculty_institution_occurrence["n_institutions_in_pub"]
        )
    )

    publication_faculty_institution_occurrence["source"] = publication_faculty_institution_occurrence["kar_code"]
    publication_faculty_institution_occurrence["target"] = publication_faculty_institution_occurrence["inst_id"]

    # ---- 4. aggregált kar ↔ intézmény élek ----
    agg_cols_fac_inst = [
        "kar_code",
        "inst_id",
        "inst_name_canonical",
        "country",
        "country_code",
        "is_hungary",
    ]
    agg_cols_fac_inst = [c for c in agg_cols_fac_inst if c in publication_faculty_institution_occurrence.columns]

    faculty_institution_edges = (
        publication_faculty_institution_occurrence
        .groupby(agg_cols_fac_inst, dropna=False)
        .agg(
            pub_count_raw=("pub_id", "nunique"),
            weight_frac=("weight_frac_fac_inst", "sum"),
            min_n_kars_in_pub=("n_kars_in_pub", "min"),
            max_n_kars_in_pub=("n_kars_in_pub", "max"),
            min_n_institutions_in_pub=("n_institutions_in_pub", "min"),
            max_n_institutions_in_pub=("n_institutions_in_pub", "max"),
        )
        .reset_index()
    )

    faculty_institution_edges["source"] = faculty_institution_edges["kar_code"]
    faculty_institution_edges["target"] = faculty_institution_edges["inst_id"]

    faculty_institution_edges = faculty_institution_edges.sort_values(
        ["weight_frac", "pub_count_raw", "kar_code", "inst_name_canonical"],
        ascending=[False, False, True, True],
        kind="stable"
    ).reset_index(drop=True)

    audit = pd.Series({
        "n_publication_de_institution_rows": int(len(publication_de_institution_occurrence)),
        "n_de_institution_edges": int(len(de_institution_edges)),
        "n_publication_faculty_institution_rows": int(len(publication_faculty_institution_occurrence)),
        "n_faculty_institution_edges": int(len(faculty_institution_edges)),
        "n_unique_external_institutions": int(pil["inst_id"].nunique()) if not pil.empty else 0,
        "n_hungarian_external_institutions": int(
            pil.loc[pil["is_hungary"] == True, "inst_id"].nunique()
        ) if "is_hungary" in pil.columns and not pil.empty else 0,
        "n_nonhungarian_external_institutions": int(
            pil.loc[pil["is_hungary"] == False, "inst_id"].nunique()
        ) if "is_hungary" in pil.columns and not pil.empty else 0,
    })

    return (
        publication_de_institution_occurrence,
        de_institution_edges,
        publication_faculty_institution_occurrence,
        faculty_institution_edges,
        audit,
    )


def build_country_aggregations(
    publication_country_occurrence: pd.DataFrame,
    publication_faculty_link: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """DE–külföldi ország és kar–külföldi ország háló publikációszintű adatokból.

    A Country/Region lista közvetlen publikáció–ország reláció, nem
    intézmény–ország reláció. Minden vizsgált DE-publikációban szerepel
    Magyarország, ezért HUN nem jelent önálló külső partnerországot.

    Minden cikk m különböző külföldi országot és k DE-kart tartalmazhat.
    - DE–ország nyers érték: adott országot tartalmazó cikkek száma
    - DE–ország tört súly: 1/m publikációnként
    - kar–ország tört súly: 1/(k*m) publikációnként
    Az országlisták NEM állítják, hogy melyik konkrét intézmény melyik
    országhoz tartozott; intézményi címkézésre nem használhatók.
    """
    pco = publication_country_occurrence[["pub_id", "country", "country_code"]].copy()
    pco = pco.dropna(subset=["pub_id", "country_code"])
    pco["country_code"] = pco["country_code"].astype(str).str.strip()
    pco = pco.loc[(pco["country_code"] != "") & (pco["country_code"] != "HUN")].copy()
    pco = pco.drop_duplicates(subset=["pub_id", "country_code"], keep="first")

    keep_cols_de = ["country", "country_code", "is_hungary", "pub_count_raw",
                    "weight_frac", "source", "target"]
    keep_cols_fac = ["kar_code"] + keep_cols_de

    if pco.empty:
        empty_de = pd.DataFrame(columns=keep_cols_de)
        empty_fac = pd.DataFrame(columns=keep_cols_fac)
        audit = pd.Series({"n_de_country_edges": 0, "n_faculty_country_edges": 0,
                           "n_unique_countries_total": 0, "n_publications_with_foreign_country": 0,
                           "n_hungarian_country_edges_de": 0, "n_nonhungarian_country_edges_de": 0})
        return empty_de, empty_fac, audit

    pco["n_foreign_countries_in_pub"] = pco.groupby("pub_id")["country_code"].transform("size")
    pco["country_weight_frac"] = 1.0 / pco["n_foreign_countries_in_pub"]

    de_country_edges = (
        pco.groupby("country_code", as_index=False)
        .agg(country=("country", "first"),
             pub_count_raw=("pub_id", "nunique"),
             weight_frac=("country_weight_frac", "sum"))
    )
    de_country_edges["is_hungary"] = False
    de_country_edges["source"] = "DE"
    de_country_edges["target"] = de_country_edges["country_code"]
    de_country_edges = de_country_edges.sort_values(
        ["weight_frac", "pub_count_raw", "country"],
        ascending=[False, False, True], kind="stable"
    ).reset_index(drop=True)
    de_country_edges = de_country_edges[keep_cols_de]

    pfl = (publication_faculty_link[["pub_id", "kar_code"]]
           .dropna().drop_duplicates().copy())
    pfl["n_faculties_in_pub"] = pfl.groupby("pub_id")["kar_code"].transform("size")
    joint = pfl.merge(pco, on="pub_id", how="inner", validate="many_to_many")
    joint["faculty_country_weight_frac"] = (
        1.0 / (joint["n_faculties_in_pub"] * joint["n_foreign_countries_in_pub"])
    )
    faculty_country_edges = (
        joint.groupby(["kar_code", "country_code"], as_index=False)
        .agg(country=("country", "first"),
             pub_count_raw=("pub_id", "nunique"),
             weight_frac=("faculty_country_weight_frac", "sum"))
    )
    faculty_country_edges["is_hungary"] = False
    faculty_country_edges["source"] = faculty_country_edges["kar_code"]
    faculty_country_edges["target"] = faculty_country_edges["country_code"]
    faculty_country_edges = faculty_country_edges.sort_values(
        ["weight_frac", "pub_count_raw", "kar_code", "country"],
        ascending=[False, False, True, True], kind="stable"
    ).reset_index(drop=True)
    faculty_country_edges = faculty_country_edges[keep_cols_fac]

    # Frakcionált ellenőrzés: minden külföldi résztvevőt tartalmazó
    # publikáció DE-szinten 1, kari szinten is összesen 1 súlyt ad.
    total_pubs_foreign = pco["pub_id"].nunique()
    assert np.isclose(de_country_edges["weight_frac"].sum(), total_pubs_foreign)
    assert np.isclose(faculty_country_edges["weight_frac"].sum(), total_pubs_foreign)

    audit = pd.Series({
        "n_de_country_edges": int(len(de_country_edges)),
        "n_faculty_country_edges": int(len(faculty_country_edges)),
        "n_unique_countries_total": int(de_country_edges["country_code"].nunique()),
        "n_publications_with_foreign_country": int(total_pubs_foreign),
        "n_hungarian_country_edges_de": 0,
        "n_nonhungarian_country_edges_de": int(len(de_country_edges)),
        "total_fractional_weight_de": float(de_country_edges["weight_frac"].sum()),
        "total_fractional_weight_faculties": float(faculty_country_edges["weight_frac"].sum()),
    })
    return de_country_edges, faculty_country_edges, audit


def _build_undirected_graph_with_distance(
    nodes_df: pd.DataFrame,
    node_id_col: str,
    edges_df: pd.DataFrame,
    source_col: str = "source",
    target_col: str = "target",
    weight_col: str = "weight",
) -> nx.Graph:
    """
    Súlyozott, irányítatlan gráf építése úgy, hogy a súlyból distance is képződik:
    distance = 1 / weight
    """
    G = nx.Graph()

    node_ids = nodes_df[node_id_col].astype(str).tolist()
    G.add_nodes_from(node_ids)

    for _, row in edges_df.iterrows():
        s = str(row[source_col])
        t = str(row[target_col])
        w = float(row[weight_col])

        if s == t:
            continue
        if w <= 0:
            continue

        G.add_edge(s, t, weight=w, distance=1.0 / w)

    return G


def compute_author_network_metrics(
    author_nodes_export: pd.DataFrame,
    author_author_edges: pd.DataFrame,
    node_id_col: str = "author_id",
    weight_col: str = "weight",
    betweenness_k: int = 500,
    random_seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Szerzőháló metrikák számítása.

    A betweenness itt approximált:
    - unweighted betweenness: k mintavételes
    - weighted betweenness: k mintavételes, distance = 1 / weight
    """
    nodes = author_nodes_export.copy()
    nodes[node_id_col] = nodes[node_id_col].astype(str)

    edges = author_author_edges[["source", "target", weight_col]].copy()

    G = _build_undirected_graph_with_distance(
        nodes_df=nodes,
        node_id_col=node_id_col,
        edges_df=edges,
        source_col="source",
        target_col="target",
        weight_col=weight_col,
    )

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    # Alap metrikák
    degree_dict = dict(G.degree())
    strength_dict = dict(G.degree(weight="weight"))
    pagerank_dict = nx.pagerank(G, weight="weight") if n_edges > 0 else {n: 0.0 for n in G.nodes()}

    # Komponensek
    comp_rows = []
    for comp_id, comp_nodes in enumerate(nx.connected_components(G), start=1):
        comp_nodes = set(comp_nodes)
        comp_size = len(comp_nodes)
        for n in comp_nodes:
            comp_rows.append({
                node_id_col: n,
                "author_component_id": comp_id,
                "author_component_size": comp_size,
            })
    comp_df = pd.DataFrame(comp_rows)

    # Approx betweenness
    if n_edges > 0:
        k_eff = min(betweenness_k, n_nodes)
        btw_unweighted = nx.betweenness_centrality(
            G, k=k_eff, normalized=True, seed=random_seed
        )
        btw_weighted = nx.betweenness_centrality(
            G, k=k_eff, normalized=True, weight="distance", seed=random_seed
        )
    else:
        btw_unweighted = {n: 0.0 for n in G.nodes()}
        btw_weighted = {n: 0.0 for n in G.nodes()}

    metrics_df = pd.DataFrame({
        node_id_col: list(G.nodes()),
        "author_degree": [degree_dict.get(n, 0) for n in G.nodes()],
        "author_strength": [strength_dict.get(n, 0.0) for n in G.nodes()],
        "author_betweenness": [btw_unweighted.get(n, 0.0) for n in G.nodes()],
        "author_betweenness_weighted": [btw_weighted.get(n, 0.0) for n in G.nodes()],
        "author_pagerank_weighted": [pagerank_dict.get(n, 0.0) for n in G.nodes()],
    })

    out = nodes.merge(metrics_df, on=node_id_col, how="left")
    out = out.merge(comp_df, on=node_id_col, how="left")

    for col in [
        "author_degree",
        "author_strength",
        "author_betweenness",
        "author_betweenness_weighted",
        "author_pagerank_weighted",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["author_degree"] = out["author_degree"].astype(int)
    out["author_component_id"] = pd.to_numeric(out["author_component_id"], errors="coerce").fillna(0).astype(int)
    out["author_component_size"] = pd.to_numeric(out["author_component_size"], errors="coerce").fillna(1).astype(int)

    audit = pd.Series({
        "n_author_nodes": int(n_nodes),
        "n_author_edges": int(n_edges),
        "n_author_components": int(nx.number_connected_components(G)) if n_nodes > 0 else 0,
        "largest_author_component_size": int(max((len(c) for c in nx.connected_components(G)), default=0)),
        "betweenness_k_used": int(min(betweenness_k, n_nodes)),
    })

    return out, audit


def compute_faculty_network_metrics(
    faculty_nodes_export: pd.DataFrame,
    faculty_faculty_edges: pd.DataFrame,
    node_id_col: str = "kar_code",
    weight_col: str = "weight_frac",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Kari háló metrikák számítása.

    Itt exact számolás megy.
    A self-loopokat eldobjuk a metrikák előtt.
    """
    nodes = faculty_nodes_export.copy()
    nodes[node_id_col] = nodes[node_id_col].astype(str)

    edges = faculty_faculty_edges.loc[
        ~faculty_faculty_edges["is_self_loop"],
        ["source", "target", weight_col]
    ].copy()

    G = _build_undirected_graph_with_distance(
        nodes_df=nodes,
        node_id_col=node_id_col,
        edges_df=edges,
        source_col="source",
        target_col="target",
        weight_col=weight_col,
    )

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    degree_dict = dict(G.degree())
    strength_dict = dict(G.degree(weight="weight"))
    pagerank_dict = nx.pagerank(G, weight="weight") if n_edges > 0 else {n: 0.0 for n in G.nodes()}

    if n_edges > 0:
        btw_unweighted = nx.betweenness_centrality(G, normalized=True)
        btw_weighted = nx.betweenness_centrality(G, normalized=True, weight="distance")
    else:
        btw_unweighted = {n: 0.0 for n in G.nodes()}
        btw_weighted = {n: 0.0 for n in G.nodes()}

    comp_rows = []
    for comp_id, comp_nodes in enumerate(nx.connected_components(G), start=1):
        comp_nodes = set(comp_nodes)
        comp_size = len(comp_nodes)
        for n in comp_nodes:
            comp_rows.append({
                node_id_col: n,
                "faculty_component_id": comp_id,
                "faculty_component_size": comp_size,
            })
    comp_df = pd.DataFrame(comp_rows)

    metrics_df = pd.DataFrame({
        node_id_col: list(G.nodes()),
        "faculty_degree": [degree_dict.get(n, 0) for n in G.nodes()],
        "faculty_strength_weight_frac": [strength_dict.get(n, 0.0) for n in G.nodes()],
        "faculty_betweenness": [btw_unweighted.get(n, 0.0) for n in G.nodes()],
        "faculty_betweenness_weighted": [btw_weighted.get(n, 0.0) for n in G.nodes()],
        "faculty_pagerank_weighted": [pagerank_dict.get(n, 0.0) for n in G.nodes()],
    })

    out = nodes.merge(metrics_df, on=node_id_col, how="left")
    out = out.merge(comp_df, on=node_id_col, how="left")

    for col in [
        "faculty_degree",
        "faculty_strength_weight_frac",
        "faculty_betweenness",
        "faculty_betweenness_weighted",
        "faculty_pagerank_weighted",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["faculty_degree"] = out["faculty_degree"].astype(int)
    out["faculty_component_id"] = pd.to_numeric(out["faculty_component_id"], errors="coerce").fillna(0).astype(int)
    out["faculty_component_size"] = pd.to_numeric(out["faculty_component_size"], errors="coerce").fillna(1).astype(int)

    audit = pd.Series({
        "n_faculty_nodes": int(n_nodes),
        "n_faculty_edges_no_self_loops": int(n_edges),
        "n_faculty_components": int(nx.number_connected_components(G)) if n_nodes > 0 else 0,
        "largest_faculty_component_size": int(max((len(c) for c in nx.connected_components(G)), default=0)),
    })

    return out, audit


def build_gephi_exports(
    author_nodes_export_enriched: pd.DataFrame,
    author_author_edges: pd.DataFrame,
    faculty_nodes_export_enriched: pd.DataFrame,
    faculty_faculty_edges: pd.DataFrame,
    institution_dict: pd.DataFrame,
    de_institution_edges: pd.DataFrame,
    faculty_institution_edges: pd.DataFrame,
    de_country_edges: pd.DataFrame,
    faculty_country_edges: pd.DataFrame,
) -> tuple[
    pd.DataFrame, pd.DataFrame,
    pd.DataFrame, pd.DataFrame,
    pd.DataFrame, pd.DataFrame, pd.DataFrame,
    pd.DataFrame, pd.DataFrame,
    pd.Series
]:
    """
    A végső Gephi-kompatibilis node és edge táblák előállítása.
    """
    # ---- Author nodes / edges ----
    author_nodes_gephi = author_nodes_export_enriched.copy()
    if "Id" not in author_nodes_gephi.columns:
        author_nodes_gephi["Id"] = author_nodes_gephi["author_id"]
    if "Label" not in author_nodes_gephi.columns:
        author_nodes_gephi["Label"] = author_nodes_gephi["canonical_name"]

    author_edges_gephi = author_author_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight": "Weight",
    })

    # ---- Faculty nodes / edges ----
    faculty_nodes_gephi = faculty_nodes_export_enriched.copy()
    if "Id" not in faculty_nodes_gephi.columns:
        faculty_nodes_gephi["Id"] = faculty_nodes_gephi["kar_code"]
    if "Label" not in faculty_nodes_gephi.columns:
        faculty_nodes_gephi["Label"] = faculty_nodes_gephi["kar_code"]

    faculty_edges_gephi = faculty_faculty_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight_frac": "Weight",
    })

    # ---- Institution nodes / edges ----
    institution_nodes_gephi = institution_dict.copy()
    institution_nodes_gephi["Id"] = institution_nodes_gephi["inst_id"]
    institution_nodes_gephi["Label"] = institution_nodes_gephi["inst_name_canonical"]

    de_institution_edges_gephi = de_institution_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight_frac": "Weight",
    })

    faculty_institution_edges_gephi = faculty_institution_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight_frac": "Weight",
    })

    # ---- Country edges ----
    de_country_edges_gephi = de_country_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight_frac": "Weight",
    })

    faculty_country_edges_gephi = faculty_country_edges.copy().rename(columns={
        "source": "Source",
        "target": "Target",
        "weight_frac": "Weight",
    })

    # ---- rendezés ----
    if {"Id", "Label"}.issubset(author_nodes_gephi.columns):
        author_nodes_gephi = author_nodes_gephi.sort_values(["Id"], kind="stable").reset_index(drop=True)
    if {"Source", "Target"}.issubset(author_edges_gephi.columns):
        author_edges_gephi = author_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)

    if {"Id", "Label"}.issubset(faculty_nodes_gephi.columns):
        faculty_nodes_gephi = faculty_nodes_gephi.sort_values(["Id"], kind="stable").reset_index(drop=True)
    if {"Source", "Target"}.issubset(faculty_edges_gephi.columns):
        faculty_edges_gephi = faculty_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)

    if {"Id", "Label"}.issubset(institution_nodes_gephi.columns):
        institution_nodes_gephi = institution_nodes_gephi.sort_values(["Id"], kind="stable").reset_index(drop=True)
    if {"Source", "Target"}.issubset(de_institution_edges_gephi.columns):
        de_institution_edges_gephi = de_institution_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)
    if {"Source", "Target"}.issubset(faculty_institution_edges_gephi.columns):
        faculty_institution_edges_gephi = faculty_institution_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)

    if {"Source", "Target"}.issubset(de_country_edges_gephi.columns):
        de_country_edges_gephi = de_country_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)
    if {"Source", "Target"}.issubset(faculty_country_edges_gephi.columns):
        faculty_country_edges_gephi = faculty_country_edges_gephi.sort_values(["Source", "Target"], kind="stable").reset_index(drop=True)

    audit = pd.Series({
        "n_author_nodes_gephi": int(len(author_nodes_gephi)),
        "n_author_edges_gephi": int(len(author_edges_gephi)),
        "n_faculty_nodes_gephi": int(len(faculty_nodes_gephi)),
        "n_faculty_edges_gephi": int(len(faculty_edges_gephi)),
        "n_institution_nodes_gephi": int(len(institution_nodes_gephi)),
        "n_de_institution_edges_gephi": int(len(de_institution_edges_gephi)),
        "n_faculty_institution_edges_gephi": int(len(faculty_institution_edges_gephi)),
        "n_de_country_edges_gephi": int(len(de_country_edges_gephi)),
        "n_faculty_country_edges_gephi": int(len(faculty_country_edges_gephi)),
    })

    return (
        author_nodes_gephi,
        author_edges_gephi,
        faculty_nodes_gephi,
        faculty_edges_gephi,
        institution_nodes_gephi,
        de_institution_edges_gephi,
        faculty_institution_edges_gephi,
        de_country_edges_gephi,
        faculty_country_edges_gephi,
        audit,
    )