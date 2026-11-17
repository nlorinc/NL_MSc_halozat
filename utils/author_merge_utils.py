"""
Szerzőazonosítási és összevonási segédfüggvények.
"""

from __future__ import annotations
from collections import defaultdict

import numpy as np
import pandas as pd


def flag_de_author_occurrences(
    publication_author_occurrence: pd.DataFrame,
    de_author_ref: pd.DataFrame,
    occurrence_id_col: str = "scopus_author_id",
    ref_id_col: str = "ref_scopus_id",
    occurrence_name_col: str = "author_name_raw",
    ref_name_col: str = "ref_author_name",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Megjelöli, hogy a szerző-előfordulások közül melyek egyeznek a
    DE szerzőtörzzsel Scopus ID alapján.

    A tényleges DE-jelölés csak Scopus ID exact match alapján történik.
    Az exact name match csak diagnosztikai segédinformáció.
    """
    occ = publication_author_occurrence.copy()
    ref = de_author_ref.copy()

    ref_min = ref[[c for c in [ref_id_col, ref_name_col] if c in ref.columns]].copy()
    ref_min = ref_min.dropna(subset=[ref_id_col]).drop_duplicates(subset=[ref_id_col], keep="first")

    ref_min = ref_min.rename(columns={
        ref_id_col: "matched_ref_scopus_id",
        ref_name_col: "matched_ref_name",
    })

    out = occ.merge(
        ref_min,
        left_on=occurrence_id_col,
        right_on="matched_ref_scopus_id",
        how="left"
    )

    out["is_de_author_ref_match"] = out["matched_ref_scopus_id"].notna()
    out["match_type"] = None
    out.loc[out["is_de_author_ref_match"], "match_type"] = "scopus_id_exact"

    # Diagnosztikai exact name check a még nem matched sorokra
    if ref_name_col in ref.columns and occurrence_name_col in out.columns:
        ref_names = set(ref[ref_name_col].dropna().astype(str).str.strip())
        out["has_exact_name_in_ref"] = (
            out[occurrence_name_col]
            .astype(str)
            .str.strip()
            .isin(ref_names)
        )
        out.loc[out[occurrence_name_col].isna(), "has_exact_name_in_ref"] = False
    else:
        out["has_exact_name_in_ref"] = False

    audit = pd.Series({
        "n_occurrence_rows": len(out),
        "n_de_matched_rows": int(out["is_de_author_ref_match"].sum()),
        "n_non_de_rows": int((~out["is_de_author_ref_match"]).sum()),
        "n_unique_matched_de_scopus_ids": int(
            out.loc[out["is_de_author_ref_match"], occurrence_id_col].nunique(dropna=True)
        ),
        "n_unmatched_but_exact_name_in_ref": int(
            ((~out["is_de_author_ref_match"]) & (out["has_exact_name_in_ref"])).sum()
        ),
    })

    return out, audit


def build_author_kar_evidence_round1(
    publication_author_occurrence_deflag: pd.DataFrame,
    publication_faculty_link: pd.DataFrame,
    pub_id_col: str = "pub_id",
    kar_col: str = "kar_code",
    de_flag_col: str = "is_de_author_ref_match",
    ref_id_col: str = "matched_ref_scopus_id",
    ref_name_col: str = "matched_ref_name",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    1. körös szerző -> kar evidence felépítése.

    Logika:
    - csak olyan publikációk kellenek, amelyek pontosan 1 DE karhoz tartoznak
    - csak a biztos DE-szerzők (exact Scopus ID match) maradnak
    - minden ilyen szerző az adott publikáció egyetlen karához kap evidence-et
    """
    occ = publication_author_occurrence_deflag.copy()
    pfl = publication_faculty_link.copy()

    # Pontosan 1 karhoz tartozó publikációk
    pub_kar_counts = (
        pfl.groupby(pub_id_col)[kar_col]
        .nunique()
        .reset_index(name="n_kars")
    )

    single_kar_pubs = pub_kar_counts.loc[
        pub_kar_counts["n_kars"] == 1,
        pub_id_col
    ]

    single_kar_map = (
        pfl.loc[pfl[pub_id_col].isin(single_kar_pubs)]
        .drop_duplicates(subset=[pub_id_col, kar_col])
        [[pub_id_col, kar_col]]
        .copy()
    )

    # Csak biztos DE-szerzők és csak 1-karos publikációk
    occ_r1 = occ.loc[
        occ[de_flag_col] &
        occ[pub_id_col].isin(single_kar_pubs)
    ].copy()

    occ_r1 = occ_r1.merge(
        single_kar_map,
        on=pub_id_col,
        how="left"
    )

    # Csak azok maradjanak, ahol valódi ref ID és kar is van
    occ_r1 = occ_r1.dropna(subset=[ref_id_col, kar_col]).copy()

    # Egy publikációban ugyanaz a DE-szerző csak egyszer számítson ugyanahhoz a karhoz
    occ_r1 = occ_r1.drop_duplicates(
        subset=[pub_id_col, ref_id_col, kar_col],
        keep="first"
    ).reset_index(drop=True)

    occ_r1["evidence_round"] = "round1_single_kar_publication"

    # Aggregált evidence
    author_kar_evidence_round1 = (
        occ_r1.groupby([ref_id_col, ref_name_col, kar_col], dropna=False)
        .agg(
            n_publications_round1=(pub_id_col, "nunique"),
            n_occurrence_rows_round1=(pub_id_col, "size"),
        )
        .reset_index()
        .rename(columns={
            ref_id_col: "ref_scopus_id",
            ref_name_col: "ref_author_name",
            kar_col: "kar_code",
        })
        .sort_values(
            ["n_publications_round1", "ref_author_name", "kar_code"],
            ascending=[False, True, True],
            kind="stable"
        )
        .reset_index(drop=True)
    )

    author_multi_kar_round1 = (
        author_kar_evidence_round1.groupby("ref_scopus_id")["kar_code"]
        .nunique()
        .reset_index(name="n_kars_round1")
    )

    audit = pd.Series({
        "n_single_kar_publications": int(len(single_kar_pubs)),
        "n_de_occurrence_rows_in_round1": int(len(occ_r1)),
        "n_unique_de_authors_round1": int(author_kar_evidence_round1["ref_scopus_id"].nunique()) if not author_kar_evidence_round1.empty else 0,
        "n_author_kar_pairs_round1": int(len(author_kar_evidence_round1)),
        "n_authors_with_multiple_kars_round1": int((author_multi_kar_round1["n_kars_round1"] > 1).sum()) if not author_multi_kar_round1.empty else 0,
    })

    return occ_r1, author_kar_evidence_round1, audit

def build_author_kar_evidence_round2(
    publication_author_occurrence_deflag: pd.DataFrame,
    publication_faculty_link: pd.DataFrame,
    publication_institution_link: pd.DataFrame,
    de_author_ref: pd.DataFrame,
    author_kar_evidence_round1: pd.DataFrame,
    pub_id_col: str = "pub_id",
    kar_col: str = "kar_code",
    de_flag_col: str = "is_de_author_ref_match",
    exact_name_flag_col: str = "has_exact_name_in_ref",
    author_name_col: str = "author_name_raw",
    ref_name_col: str = "ref_author_name",
    ref_id_col: str = "ref_scopus_id",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    2. körös szerző -> kar evidence felépítése.

    Logika:
    - csak olyan publikációk kellenek, amelyek pontosan 1 DE karhoz tartoznak
    - és van bennük legalább 1 külső intézmény
    - csak olyan occurrence sorokat használunk, amelyek:
        * NEM exact Scopus ID match-ek
        * de exact névegyezést mutatnak a DE referencia-törzzsel
    - csak azokat a neveket engedjük tovább, amelyek a DE referencia-törzsben
      egyértelműen pontosan 1 Scopus ID-hoz tartoznak
    """
    occ = publication_author_occurrence_deflag.copy()
    pfl = publication_faculty_link.copy()
    pil = publication_institution_link.copy()
    ref = de_author_ref.copy()

    # 1 karos publikációk
    pub_kar_counts = (
        pfl.groupby(pub_id_col)[kar_col]
        .nunique()
        .reset_index(name="n_kars")
    )

    single_kar_pubs = set(
        pub_kar_counts.loc[pub_kar_counts["n_kars"] == 1, pub_id_col].tolist()
    )

    single_kar_map = (
        pfl.loc[pfl[pub_id_col].isin(single_kar_pubs)]
        .drop_duplicates(subset=[pub_id_col, kar_col])
        [[pub_id_col, kar_col]]
        .copy()
    )

    # Külső intézménnyel rendelkező publikációk
    pubs_with_external = set(pil[pub_id_col].dropna().astype(str).tolist())
    target_pubs = single_kar_pubs.intersection(pubs_with_external)

    # Egyértelmű name -> ref_scopus_id mapping
    ref_name_map = ref[[ref_name_col, ref_id_col]].dropna().copy()

    name_id_counts = (
        ref_name_map.groupby(ref_name_col)[ref_id_col]
        .nunique()
        .reset_index(name="n_ref_ids_for_name")
    )

    unambiguous_names = set(
        name_id_counts.loc[name_id_counts["n_ref_ids_for_name"] == 1, ref_name_col].tolist()
    )

    ref_name_unique = (
        ref_name_map.loc[ref_name_map[ref_name_col].isin(unambiguous_names)]
        .drop_duplicates(subset=[ref_name_col], keep="first")
        .rename(columns={
            ref_name_col: "matched_by_name_ref_author_name",
            ref_id_col: "matched_by_name_ref_scopus_id",
        })
        .copy()
    )

    # Csak olyan referencia-ID-k maradjanak, amelyek már az 1. körben is kaptak evidence-et
    round1_ref_ids = set(
        author_kar_evidence_round1["ref_scopus_id"]
        .dropna()
        .astype(str)
        .tolist()
    )

    ref_name_unique["matched_by_name_ref_scopus_id"] = (
        ref_name_unique["matched_by_name_ref_scopus_id"]
        .astype(str)
    )

    ref_name_unique = ref_name_unique.loc[
        ref_name_unique["matched_by_name_ref_scopus_id"].isin(round1_ref_ids)
    ].copy()

    # Csak olyan szerző-kar párok maradhatnak, amelyek az 1. körben már léteztek
    round1_author_kar_pairs = set(
        author_kar_evidence_round1[["ref_scopus_id", "kar_code"]]
        .dropna()
        .astype(str)
        .apply(tuple, axis=1)
        .tolist()
    )

    # Kandidátusok: exact name in ref, de nincs exact Scopus ID match
    occ_r2 = occ.loc[
        (~occ[de_flag_col]) &
        (occ[exact_name_flag_col]) &
        (occ[pub_id_col].isin(target_pubs))
    ].copy()

    n_candidate_occ_rows_before_name_uniqueness = len(occ_r2)

    occ_r2 = occ_r2.merge(
        single_kar_map,
        on=pub_id_col,
        how="left"
    )

    occ_r2 = occ_r2.merge(
        ref_name_unique,
        left_on=author_name_col,
        right_on="matched_by_name_ref_author_name",
        how="left"
    )

    occ_r2 = occ_r2.dropna(subset=["matched_by_name_ref_scopus_id", kar_col]).copy()

    occ_r2["matched_by_name_ref_scopus_id"] = occ_r2["matched_by_name_ref_scopus_id"].astype(str)
    occ_r2[kar_col] = occ_r2[kar_col].astype(str)

    occ_r2["round1_author_kar_pair_exists"] = (
        occ_r2[["matched_by_name_ref_scopus_id", kar_col]]
        .apply(tuple, axis=1)
        .isin(round1_author_kar_pairs)
    )

    occ_r2 = occ_r2.loc[
        occ_r2["round1_author_kar_pair_exists"]
    ].copy()

    occ_r2 = occ_r2.drop_duplicates(
        subset=[pub_id_col, "matched_by_name_ref_scopus_id", kar_col],
        keep="first"
    ).reset_index(drop=True)

    occ_r2["evidence_round"] = "round2_single_kar_external_unique_name"

    author_kar_evidence_round2 = (
        occ_r2.groupby(
            ["matched_by_name_ref_scopus_id", "matched_by_name_ref_author_name", kar_col],
            dropna=False
        )
        .agg(
            n_publications_round2=(pub_id_col, "nunique"),
            n_occurrence_rows_round2=(pub_id_col, "size"),
        )
        .reset_index()
        .rename(columns={
            "matched_by_name_ref_scopus_id": "ref_scopus_id",
            "matched_by_name_ref_author_name": "ref_author_name",
            kar_col: "kar_code",
        })
        .sort_values(
            ["n_publications_round2", "ref_author_name", "kar_code"],
            ascending=[False, True, True],
            kind="stable"
        )
        .reset_index(drop=True)
    )

    author_multi_kar_round2 = (
        author_kar_evidence_round2.groupby("ref_scopus_id")["kar_code"]
        .nunique()
        .reset_index(name="n_kars_round2")
    )

    audit = pd.Series({
        "n_single_kar_with_external_publications": int(len(target_pubs)),
        "n_candidate_occ_rows_before_name_uniqueness": int(n_candidate_occ_rows_before_name_uniqueness),
        "n_occ_rows_round2": int(len(occ_r2)),
        "n_unique_de_authors_round2": int(author_kar_evidence_round2["ref_scopus_id"].nunique()) if not author_kar_evidence_round2.empty else 0,
        "n_author_kar_pairs_round2": int(len(author_kar_evidence_round2)),
        "n_authors_with_multiple_kars_round2": int((author_multi_kar_round2["n_kars_round2"] > 1).sum()) if not author_multi_kar_round2.empty else 0,
        "n_unambiguous_ref_names": int(len(unambiguous_names)),
        "n_round1_anchor_ref_ids": int(len(round1_ref_ids)),
        "n_round1_author_kar_pairs": int(len(round1_author_kar_pairs)),
        "n_occ_rows_after_round1_pair_filter": int(len(occ_r2)),
    })

    return occ_r2, author_kar_evidence_round2, audit

def build_author_kar_evidence_round3(
    publication_author_occurrence_deflag: pd.DataFrame,
    publication_faculty_link: pd.DataFrame,
    author_kar_evidence_round1: pd.DataFrame,
    author_kar_evidence_round2: pd.DataFrame,
    pub_id_col: str = "pub_id",
    kar_col: str = "kar_code",
    de_flag_col: str = "is_de_author_ref_match",
    matched_ref_id_col: str = "matched_ref_scopus_id",
    matched_ref_name_col: str = "matched_ref_name",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    3. körös szerző -> kar evidence felépítése.

    Logika:
    - csak többkarú publikációkat használunk
    - csak biztos DE-szerzők maradnak
    - az 1. és 2. kör alapján csak azokat a szerzőket tekintjük anchor-nak,
      akik pontosan 1 karhoz vannak már lehorgonyozva
    - ha egy többkarú publikációban az anchor szerzők minden kart lefednek
      egy kivételével, és pontosan 1 le nem horgonyzott DE-szerző marad,
      akkor ez a szerző evidence-et kap a megmaradt karhoz
    """
    occ = publication_author_occurrence_deflag.copy()
    pfl = publication_faculty_link.copy()

    # 1. és 2. kör egyesítése
    evidence_frames = []
    if len(author_kar_evidence_round1) > 0:
        evidence_frames.append(
            author_kar_evidence_round1[["ref_scopus_id", "ref_author_name", "kar_code"]].copy()
        )
    if len(author_kar_evidence_round2) > 0:
        evidence_frames.append(
            author_kar_evidence_round2[["ref_scopus_id", "ref_author_name", "kar_code"]].copy()
        )

    if len(evidence_frames) == 0:
        empty_occ = pd.DataFrame(columns=[
            "pub_id", "matched_ref_scopus_id", "matched_ref_name", "kar_code", "evidence_round"
        ])
        empty_ev = pd.DataFrame(columns=[
            "ref_scopus_id", "ref_author_name", "kar_code", "n_publications_round3", "n_occurrence_rows_round3"
        ])
        audit = pd.Series({
            "n_multi_kar_publications": 0,
            "n_single_anchor_authors": 0,
            "n_candidate_publications_round3": 0,
            "n_occ_rows_round3": 0,
            "n_unique_de_authors_round3": 0,
            "n_author_kar_pairs_round3": 0,
        })
        return empty_occ, empty_ev, audit

    all_evidence = pd.concat(evidence_frames, ignore_index=True).drop_duplicates()

    # Anchor szerzők: pontosan 1 kar
    anchor_map = (
        all_evidence.groupby(["ref_scopus_id", "ref_author_name"], dropna=False)["kar_code"]
        .agg(lambda s: sorted(set(s.dropna().astype(str))))
        .reset_index(name="kar_list")
    )

    anchor_map["n_anchor_kars"] = anchor_map["kar_list"].map(len)

    anchor_map = anchor_map.loc[anchor_map["n_anchor_kars"] == 1].copy()
    anchor_map["anchor_kar"] = anchor_map["kar_list"].str[0]

    # Többkarú publikációk
    pub_kar_map = (
        pfl.groupby(pub_id_col)[kar_col]
        .agg(lambda s: sorted(set(s.dropna().astype(str))))
        .reset_index(name="pub_kar_list")
    )
    pub_kar_map["n_pub_kars"] = pub_kar_map["pub_kar_list"].map(len)

    multi_kar_pubs = set(
        pub_kar_map.loc[pub_kar_map["n_pub_kars"] > 1, pub_id_col].tolist()
    )

    pub_kar_lookup = {
        row[pub_id_col]: set(row["pub_kar_list"])
        for _, row in pub_kar_map.loc[pub_kar_map[pub_id_col].isin(multi_kar_pubs)].iterrows()
    }

    # Csak biztos DE-szerzők a többkarú publikációkban
    occ_r3_base = occ.loc[
        occ[de_flag_col] &
        occ[pub_id_col].isin(multi_kar_pubs)
    ].copy()

    occ_r3_base = occ_r3_base.dropna(subset=[matched_ref_id_col]).copy()

    occ_r3_base[matched_ref_id_col] = occ_r3_base[matched_ref_id_col].astype(str)

    occ_r3_base = occ_r3_base.merge(
        anchor_map[["ref_scopus_id", "anchor_kar"]],
        left_on=matched_ref_id_col,
        right_on="ref_scopus_id",
        how="left"
    )

    rows = []
    n_candidate_publications_round3 = 0

    for pub_id, grp in occ_r3_base.groupby(pub_id_col, sort=False):
        pub_kars = pub_kar_lookup.get(pub_id, set())
        if len(pub_kars) <= 1:
            continue

        grp_pub = (
            grp.drop_duplicates(subset=[matched_ref_id_col], keep="first")
            .copy()
        )

        anchored = grp_pub.loc[grp_pub["anchor_kar"].notna()].copy()
        unanchored = grp_pub.loc[grp_pub["anchor_kar"].isna()].copy()

        anchored_kars = set(anchored["anchor_kar"].astype(str).tolist())
        remaining_kars = pub_kars - anchored_kars

        if len(remaining_kars) == 1 and len(unanchored) == 1:
            n_candidate_publications_round3 += 1
            remaining_kar = list(remaining_kars)[0]
            target = unanchored.iloc[0]

            rows.append({
                "pub_id": pub_id,
                "matched_ref_scopus_id": str(target[matched_ref_id_col]),
                "matched_ref_name": target[matched_ref_name_col],
                "kar_code": remaining_kar,
                "evidence_round": "round3_multi_kar_single_unanchored_remaining_kar",
            })

    author_kar_occurrence_round3 = pd.DataFrame(rows)

    if not author_kar_occurrence_round3.empty:
        author_kar_occurrence_round3 = (
            author_kar_occurrence_round3
            .drop_duplicates(subset=["pub_id", "matched_ref_scopus_id", "kar_code"], keep="first")
            .sort_values(["pub_id", "matched_ref_scopus_id", "kar_code"], kind="stable")
            .reset_index(drop=True)
        )

        author_kar_evidence_round3 = (
            author_kar_occurrence_round3
            .groupby(["matched_ref_scopus_id", "matched_ref_name", "kar_code"], dropna=False)
            .agg(
                n_publications_round3=("pub_id", "nunique"),
                n_occurrence_rows_round3=("pub_id", "size"),
            )
            .reset_index()
            .rename(columns={
                "matched_ref_scopus_id": "ref_scopus_id",
                "matched_ref_name": "ref_author_name",
            })
            .sort_values(
                ["n_publications_round3", "ref_author_name", "kar_code"],
                ascending=[False, True, True],
                kind="stable"
            )
            .reset_index(drop=True)
        )
    else:
        author_kar_evidence_round3 = pd.DataFrame(columns=[
            "ref_scopus_id", "ref_author_name", "kar_code",
            "n_publications_round3", "n_occurrence_rows_round3"
        ])

    audit = pd.Series({
        "n_multi_kar_publications": int(len(multi_kar_pubs)),
        "n_single_anchor_authors": int(anchor_map["ref_scopus_id"].nunique()),
        "n_candidate_publications_round3": int(n_candidate_publications_round3),
        "n_occ_rows_round3": int(len(author_kar_occurrence_round3)),
        "n_unique_de_authors_round3": int(author_kar_evidence_round3["ref_scopus_id"].nunique()) if not author_kar_evidence_round3.empty else 0,
        "n_author_kar_pairs_round3": int(len(author_kar_evidence_round3)),
    })

    return author_kar_occurrence_round3, author_kar_evidence_round3, audit

def build_author_kar_profile(
    de_author_ref: pd.DataFrame,
    author_kar_evidence_round1: pd.DataFrame,
    author_kar_evidence_round2: pd.DataFrame,
    author_kar_evidence_round3: pd.DataFrame,
    kar_codes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Az 1-3. körös evidence táblákból felépíti a végleges szerző–kar profilt.

    Evidence-súlyozás:
    - round1: 1.0
    - round2: 1.0
    - round3: 1.0

    Jelenleg minden kör egyenlő súllyal számít, publikációszám-alapon.
    """
    frames = []

    if len(author_kar_evidence_round1) > 0:
        tmp1 = author_kar_evidence_round1[["ref_scopus_id", "ref_author_name", "kar_code", "n_publications_round1"]].copy()
        tmp1 = tmp1.rename(columns={"n_publications_round1": "evidence_weight"})
        tmp1["evidence_round"] = "round1"
        frames.append(tmp1)

    if len(author_kar_evidence_round2) > 0:
        tmp2 = author_kar_evidence_round2[["ref_scopus_id", "ref_author_name", "kar_code", "n_publications_round2"]].copy()
        tmp2 = tmp2.rename(columns={"n_publications_round2": "evidence_weight"})
        tmp2["evidence_round"] = "round2"
        frames.append(tmp2)

    if len(author_kar_evidence_round3) > 0:
        tmp3 = author_kar_evidence_round3[["ref_scopus_id", "ref_author_name", "kar_code", "n_publications_round3"]].copy()
        tmp3 = tmp3.rename(columns={"n_publications_round3": "evidence_weight"})
        tmp3["evidence_round"] = "round3"
        frames.append(tmp3)

    if len(frames) == 0:
        empty_profile = pd.DataFrame(columns=["ref_scopus_id", "ref_author_name", "primary_kar", "n_kars_with_evidence", "total_evidence"])
        empty_long = pd.DataFrame(columns=["ref_scopus_id", "ref_author_name", "kar_code", "evidence_weight"])
        audit = pd.Series({
            "n_authors_in_profile": 0,
            "n_authors_with_any_evidence": 0,
            "n_authors_with_inter_primary_kar": 0,
        })
        return empty_profile, empty_long, audit

    evidence_long = pd.concat(frames, ignore_index=True)

    evidence_long["ref_scopus_id"] = evidence_long["ref_scopus_id"].astype(str)

    evidence_long = (
        evidence_long
        .groupby(["ref_scopus_id", "ref_author_name", "kar_code"], dropna=False)["evidence_weight"]
        .sum()
        .reset_index()
        .sort_values(["ref_scopus_id", "evidence_weight", "kar_code"], ascending=[True, False, True], kind="stable")
        .reset_index(drop=True)
    )

    # Wide pivot karonként
    profile_wide = (
        evidence_long
        .pivot_table(
            index=["ref_scopus_id", "ref_author_name"],
            columns="kar_code",
            values="evidence_weight",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # biztosítsuk, hogy minden kar oszlopként jelen legyen
    for kar in kar_codes:
        if kar not in profile_wide.columns:
            profile_wide[kar] = 0

    kar_cols_present = [k for k in kar_codes if k in profile_wide.columns]

    profile_wide["n_kars_with_evidence"] = (profile_wide[kar_cols_present] > 0).sum(axis=1)
    profile_wide["total_evidence"] = profile_wide[kar_cols_present].sum(axis=1)

    def determine_primary_kar(row):
        values = {kar: row[kar] for kar in kar_cols_present}
        max_val = max(values.values()) if len(values) > 0 else 0

        if max_val <= 0:
            return np.nan

        best_kars = sorted([kar for kar, val in values.items() if val == max_val])

        if len(best_kars) == 1:
            return best_kars[0]

        return "INTER"

    profile_wide["primary_kar"] = profile_wide.apply(determine_primary_kar, axis=1)

    # összekötés a teljes de_author_ref-fel, hogy a nem lefedett DE szerzők is megmaradjanak
    base_ref = de_author_ref[["ref_scopus_id", "ref_author_name"]].drop_duplicates().copy()
    base_ref["ref_scopus_id"] = base_ref["ref_scopus_id"].astype(str)

    author_kar_profile = base_ref.merge(
        profile_wide,
        on=["ref_scopus_id", "ref_author_name"],
        how="left"
    )

    for kar in kar_codes:
        if kar in author_kar_profile.columns:
            author_kar_profile[kar] = author_kar_profile[kar].fillna(0)
        else:
            author_kar_profile[kar] = 0

    author_kar_profile["n_kars_with_evidence"] = author_kar_profile["n_kars_with_evidence"].fillna(0).astype(int)
    author_kar_profile["total_evidence"] = author_kar_profile["total_evidence"].fillna(0)
    author_kar_profile["primary_kar"] = author_kar_profile["primary_kar"].where(
        author_kar_profile["total_evidence"] > 0,
        np.nan
    )

    author_kar_profile = author_kar_profile.sort_values(
        ["total_evidence", "ref_author_name"],
        ascending=[False, True],
        kind="stable"
    ).reset_index(drop=True)

    audit = pd.Series({
        "n_authors_in_profile": int(len(author_kar_profile)),
        "n_authors_with_any_evidence": int((author_kar_profile["total_evidence"] > 0).sum()),
        "n_authors_without_evidence": int((author_kar_profile["total_evidence"] <= 0).sum()),
        "n_authors_with_inter_primary_kar": int((author_kar_profile["primary_kar"] == "INTER").sum()),
        "n_authors_with_single_kar_evidence": int((author_kar_profile["n_kars_with_evidence"] == 1).sum()),
        "n_authors_with_multi_kar_evidence": int((author_kar_profile["n_kars_with_evidence"] > 1).sum()),
    })

    return author_kar_profile, evidence_long, audit

def build_author_entities(
    de_author_ref: pd.DataFrame,
    author_kar_profile: pd.DataFrame,
    publication_author_occurrence_deflag: pd.DataFrame,
    kar_codes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Konzervatív szerző-entitás összevonás.

    Auto-merge feltétel:
    - exact névegyezés
    - azonos primary_kar
    - a primary_kar nem hiányzó és nem INTER
    - van közös publikáció vagy közös DE társszerző
    """
    # ---- 1. Base tábla ----
    base = de_author_ref.copy()
    base["ref_scopus_id"] = base["ref_scopus_id"].astype(str)

    profile_cols = ["ref_scopus_id", "ref_author_name", "primary_kar", "n_kars_with_evidence", "total_evidence"] + [
        k for k in kar_codes if k in author_kar_profile.columns
    ]

    profile_min = author_kar_profile[profile_cols].copy()
    profile_min["ref_scopus_id"] = profile_min["ref_scopus_id"].astype(str)

    base = base.merge(
        profile_min,
        on=["ref_scopus_id", "ref_author_name"],
        how="left"
    )

    for kar in kar_codes:
        if kar not in base.columns:
            base[kar] = 0
        base[kar] = base[kar].fillna(0)

    if "n_kars_with_evidence" not in base.columns:
        base["n_kars_with_evidence"] = 0
    if "total_evidence" not in base.columns:
        base["total_evidence"] = 0

    base["n_kars_with_evidence"] = base["n_kars_with_evidence"].fillna(0).astype(int)
    base["total_evidence"] = base["total_evidence"].fillna(0)
    base["name_key"] = base["ref_author_name"].astype(str).str.strip()

    # ---- 2. Közös publikáció / DE társszerző jelek ----
    de_occ = publication_author_occurrence_deflag.loc[
        publication_author_occurrence_deflag["is_de_author_ref_match"]
    ].copy()

    de_occ = de_occ.dropna(subset=["matched_ref_scopus_id"]).copy()
    de_occ["matched_ref_scopus_id"] = de_occ["matched_ref_scopus_id"].astype(str)

    pubs_by_author = (
        de_occ.groupby("matched_ref_scopus_id")["pub_id"]
        .apply(lambda s: set(s.dropna().astype(str)))
        .to_dict()
    )

    coauthors_by_author = defaultdict(set)

    for pub_id, grp in de_occ.groupby("pub_id", sort=False):
        ids = sorted(set(grp["matched_ref_scopus_id"].dropna().astype(str).tolist()))
        for a in ids:
            for b in ids:
                if a != b:
                    coauthors_by_author[a].add(b)

    # ---- 3. Exact-name csoportok és auto-merge komponensek ----
    entity_groups = []   # list[list[index]]
    review_rows = []

    def shared_signal(id_a: str, id_b: str) -> tuple[bool, int, int]:
        pubs_a = pubs_by_author.get(id_a, set())
        pubs_b = pubs_by_author.get(id_b, set())
        shared_pubs = len(pubs_a.intersection(pubs_b))

        co_a = coauthors_by_author.get(id_a, set())
        co_b = coauthors_by_author.get(id_b, set())
        shared_coauthors = len(co_a.intersection(co_b))

        signal = (shared_pubs > 0) or (shared_coauthors > 0)
        return signal, shared_pubs, shared_coauthors

    for name_key, grp in base.groupby("name_key", sort=False):
        idxs = grp.index.tolist()

        if len(idxs) == 1:
            entity_groups.append(idxs)
            continue

        grp_non_inter = grp.loc[
            grp["primary_kar"].notna() &
            (grp["primary_kar"] != "INTER")
        ].copy()

        unique_primary_kars = sorted(set(grp_non_inter["primary_kar"].astype(str).tolist()))

        if len(unique_primary_kars) != 1:
            # Nem merge-ölünk, csak review
            for idx in idxs:
                entity_groups.append([idx])

            review_rows.append({
                "name_key": name_key,
                "n_ref_ids": len(idxs),
                "review_reason": "ambiguous_or_missing_primary_kar",
                "primary_kars_seen": " | ".join(sorted(set(grp["primary_kar"].dropna().astype(str).tolist()))),
            })
            continue

        target_kar = unique_primary_kars[0]

        # gráf ugyanazon név és ugyanazon primary_kar mellett
        local_idxs = grp.index.tolist()
        adjacency = {idx: set() for idx in local_idxs}

        for i in range(len(local_idxs)):
            idx_i = local_idxs[i]
            row_i = grp.loc[idx_i]

            if row_i["primary_kar"] != target_kar:
                continue

            for j in range(i + 1, len(local_idxs)):
                idx_j = local_idxs[j]
                row_j = grp.loc[idx_j]

                if row_j["primary_kar"] != target_kar:
                    continue

                signal, shared_pubs, shared_coauthors = shared_signal(
                    str(row_i["ref_scopus_id"]),
                    str(row_j["ref_scopus_id"])
                )

                if signal:
                    adjacency[idx_i].add(idx_j)
                    adjacency[idx_j].add(idx_i)

        # connected components
        visited = set()
        components = []

        for idx in local_idxs:
            if idx in visited:
                continue

            stack = [idx]
            comp = []

            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                comp.append(cur)
                stack.extend(list(adjacency[cur] - visited))

            components.append(sorted(comp))

        # ha egy komponens több elemből áll, auto-merge; különben marad singleton
        n_multi_components = 0
        for comp in components:
            entity_groups.append(comp)
            if len(comp) > 1:
                n_multi_components += 1

        if n_multi_components == 0 and len(local_idxs) > 1:
            review_rows.append({
                "name_key": name_key,
                "n_ref_ids": len(local_idxs),
                "review_reason": "same_name_same_kar_but_no_shared_signal",
                "primary_kars_seen": target_kar,
            })

    # ---- 4. author_id kiosztás és members tábla ----
    member_rows = []

    for i, comp in enumerate(entity_groups, start=1):
        author_id = f"AUTH_{i:06d}"

        for idx in comp:
            row = base.loc[idx]
            member_rows.append({
                "author_id": author_id,
                "ref_scopus_id": str(row["ref_scopus_id"]),
                "ref_author_name": row["ref_author_name"],
                "source_primary_kar": row["primary_kar"],
                "source_total_evidence": row["total_evidence"],
            })

    author_entity_members = pd.DataFrame(member_rows).sort_values(
        ["author_id", "ref_author_name", "ref_scopus_id"],
        kind="stable"
    ).reset_index(drop=True)

    # ---- 5. Entitás-aggregálás ----
    work = author_entity_members.merge(
        base,
        on=["ref_scopus_id", "ref_author_name"],
        how="left"
    )

    def choose_canonical_name(series: pd.Series):
        vals = series.dropna().astype(str).tolist()
        if len(vals) == 0:
            return np.nan
        vals = sorted(vals, key=lambda x: (-len(x), x))
        return vals[0]

    def choose_primary_kar_from_row(row):
        vals = {kar: row[kar] for kar in kar_codes}
        max_val = max(vals.values()) if len(vals) > 0 else 0

        if max_val <= 0:
            return np.nan

        best = sorted([kar for kar, val in vals.items() if val == max_val])
        return best[0] if len(best) == 1 else "INTER"

    # Valamennyi szcientometriai mutató ugyanabból az eredeti Scopus-profilból származik.
    # Kiválasztás: scholarly_output, DE-affiliáció, kitöltöttség, citations, stabil ID.
    metric_cols = [
        "citations", "cit_per_pub", "fwci", "h_index", "scholarly_output",
        "most_recent_publication", "oldest_publication_since_1996",
        "primary_affiliation",
    ]
    agg_rows = []

    for author_id, grp in work.groupby("author_id", sort=False):
        candidates = grp.copy()
        candidates["_rank_output"] = pd.to_numeric(
            candidates.get("scholarly_output", pd.Series(np.nan, index=candidates.index)),
            errors="coerce",
        ).fillna(-1)
        candidates["_rank_de"] = (
            candidates.get("primary_affiliation", pd.Series("", index=candidates.index))
            .astype("string")
            .str.contains("University of Debrecen", case=False, regex=False, na=False)
            .astype(int)
        )
        available_metrics = [c for c in metric_cols if c in candidates.columns]
        candidates["_rank_completeness"] = candidates[available_metrics].notna().sum(axis=1)
        candidates["_rank_citations"] = pd.to_numeric(
            candidates.get("citations", pd.Series(np.nan, index=candidates.index)),
            errors="coerce",
        ).fillna(-1)
        candidates = candidates.sort_values(
            ["_rank_output", "_rank_de", "_rank_completeness", "_rank_citations", "ref_scopus_id"],
            ascending=[False, False, False, False, True],
            kind="stable",
        )
        representative = candidates.iloc[0]

        out = {
            "author_id": author_id,
            "canonical_name": choose_canonical_name(grp["ref_author_name"]),
            "n_scopus_ids": int(grp["ref_scopus_id"].nunique()),
            "scopus_ids_joined": " | ".join(sorted(set(grp["ref_scopus_id"].astype(str).tolist()))),
            "metric_source_scopus_id": str(representative["ref_scopus_id"]),
            "metric_selection_method": "max_output_de_affiliation_completeness_citations",
        }
        for col in metric_cols:
            out[col] = representative[col] if col in grp.columns else np.nan

        for kar in kar_codes:
            out[kar] = grp[kar].sum() if kar in grp.columns else 0

        out["n_kars_with_evidence"] = int(sum(out[kar] > 0 for kar in kar_codes))
        out["total_evidence"] = float(sum(out[kar] for kar in kar_codes))
        out["primary_kar"] = choose_primary_kar_from_row(out)

        agg_rows.append(out)

    author_entity = pd.DataFrame(agg_rows).sort_values(
        ["total_evidence", "canonical_name"],
        ascending=[False, True],
        kind="stable"
    ).reset_index(drop=True)

    author_merge_review = pd.DataFrame(review_rows).sort_values(
        ["n_ref_ids", "name_key"],
        ascending=[False, True],
        kind="stable"
    ).reset_index(drop=True) if len(review_rows) > 0 else pd.DataFrame(
        columns=["name_key", "n_ref_ids", "review_reason", "primary_kars_seen"]
    )

    multi_entities = (
        author_entity_members.groupby("author_id")["ref_scopus_id"]
        .nunique()
        .reset_index(name="n_scopus_ids")
    )

    audit = pd.Series({
        "n_ref_author_rows": int(len(base)),
        "n_author_entities": int(len(author_entity)),
        "n_multi_scopus_entities": int((multi_entities["n_scopus_ids"] > 1).sum()),
        "n_ref_rows_in_multi_scopus_entities": int(
            multi_entities.loc[multi_entities["n_scopus_ids"] > 1, "n_scopus_ids"].sum()
        ),
        "n_review_groups": int(len(author_merge_review)),
    })

    return author_entity, author_entity_members, author_merge_review, audit

def build_author_entity_scopus_id_tables(
    author_entity: pd.DataFrame,
    author_entity_members: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Az author_entity és author_entity_members táblákból létrehozza:

    - author_entity_scopus_ids_long:
        1 sor = 1 author_id – 1 ref_scopus_id kapcsolat
    - author_entity_scopus_ids:
        wide formátumú tábla: author_id + scopus_id_1, scopus_id_2, ...

    A wide tábla a felhasználói igény szerinti végleges Scopus ID-tábla,
    a long tábla pedig a későbbi joinokhoz praktikus.
    """
    members = author_entity_members.copy()
    members["ref_scopus_id"] = members["ref_scopus_id"].astype(str)

    keep_cols = [c for c in [
        "author_id",
        "ref_scopus_id",
        "ref_author_name",
        "source_primary_kar",
        "source_total_evidence",
    ] if c in members.columns]

    members = members[keep_cols].drop_duplicates().copy()

    entity_meta = author_entity[[
        "author_id",
        "canonical_name",
        "primary_kar",
        "n_scopus_ids",
        "total_evidence",
    ]].copy()

    # Long formátum
    author_entity_scopus_ids_long = members.merge(
        entity_meta,
        on="author_id",
        how="left"
    )

    if "source_total_evidence" not in author_entity_scopus_ids_long.columns:
        author_entity_scopus_ids_long["source_total_evidence"] = 0

    author_entity_scopus_ids_long["source_total_evidence"] = (
        pd.to_numeric(author_entity_scopus_ids_long["source_total_evidence"], errors="coerce")
        .fillna(0)
    )

    author_entity_scopus_ids_long = author_entity_scopus_ids_long.sort_values(
        ["author_id", "source_total_evidence", "ref_scopus_id"],
        ascending=[True, False, True],
        kind="stable"
    ).reset_index(drop=True)

    author_entity_scopus_ids_long["scopus_id_rank"] = (
        author_entity_scopus_ids_long.groupby("author_id").cumcount() + 1
    )

    # Wide formátum
    wide_ids = (
        author_entity_scopus_ids_long[["author_id", "scopus_id_rank", "ref_scopus_id"]]
        .pivot(index="author_id", columns="scopus_id_rank", values="ref_scopus_id")
        .reset_index()
    )

    wide_ids.columns = [
        "author_id" if c == "author_id" else f"scopus_id_{int(c)}"
        for c in wide_ids.columns
    ]

    author_entity_scopus_ids = entity_meta.merge(
        wide_ids,
        on="author_id",
        how="left"
    )

    # oszloprend
    scopus_cols = [c for c in author_entity_scopus_ids.columns if c.startswith("scopus_id_")]
    preferred_order = [
        "author_id",
        "canonical_name",
        "primary_kar",
        "n_scopus_ids",
        "total_evidence",
    ] + sorted(scopus_cols, key=lambda x: int(x.split("_")[-1]))

    other_cols = [c for c in author_entity_scopus_ids.columns if c not in preferred_order]
    author_entity_scopus_ids = author_entity_scopus_ids[preferred_order + other_cols]

    audit = pd.Series({
        "n_author_entities": int(author_entity["author_id"].nunique()),
        "n_author_entity_scopus_pairs": int(len(author_entity_scopus_ids_long)),
        "n_multi_scopus_entities": int((author_entity["n_scopus_ids"] > 1).sum()),
        "max_scopus_ids_per_entity": int(author_entity["n_scopus_ids"].max()) if len(author_entity) > 0 else 0,
        "n_duplicate_author_scopus_pairs": int(
            author_entity_scopus_ids_long.duplicated(subset=["author_id", "ref_scopus_id"]).sum()
        ),
    })

    return author_entity_scopus_ids, author_entity_scopus_ids_long, audit

def build_publication_author_entity_link(
    publication_author_occurrence_deflag: pd.DataFrame,
    author_entity_scopus_ids_long: pd.DataFrame,
    pub_id_col: str = "pub_id",
    de_flag_col: str = "is_de_author_ref_match",
    matched_ref_id_col: str = "matched_ref_scopus_id",
    source_kar_col: str = "source_kar",
    source_file_col: str = "source_file",
    author_position_col: str = "author_position",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    A biztosan DE-s szerző-előfordulásokat végleges author_id szintre képezi le.

    Kimenet:
    - publication_author_entity_link:
        1 sor = 1 publikáció – 1 végleges DE author entity
    """
    occ = publication_author_occurrence_deflag.copy()
    ent = author_entity_scopus_ids_long.copy()

    occ = occ.loc[occ[de_flag_col]].copy()
    occ = occ.dropna(subset=[matched_ref_id_col]).copy()
    occ[matched_ref_id_col] = occ[matched_ref_id_col].astype(str)

    ent = ent[["author_id", "ref_scopus_id", "canonical_name", "primary_kar"]].drop_duplicates().copy()
    ent["ref_scopus_id"] = ent["ref_scopus_id"].astype(str)

    work = occ.merge(
        ent,
        left_on=matched_ref_id_col,
        right_on="ref_scopus_id",
        how="left"
    )

    work = work.dropna(subset=["author_id"]).copy()

    # Aggregálás publikáció + author entity szintre
    agg = (
        work.groupby([pub_id_col, "author_id"], dropna=False)
        .agg(
            canonical_name=("canonical_name", "first"),
            primary_kar=("primary_kar", "first"),
            author_position_min=(author_position_col, "min"),
            n_occurrence_rows=("author_id", "size"),
            n_source_kars=(source_kar_col, "nunique"),
            source_kars=(source_kar_col, lambda s: " | ".join(sorted(set(s.dropna().astype(str))))),
            source_files=(source_file_col, lambda s: " | ".join(sorted(set(s.dropna().astype(str))))),
        )
        .reset_index()
        .rename(columns={pub_id_col: "pub_id"})
        .sort_values(["pub_id", "author_position_min", "author_id"], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_de_occurrence_rows_input": int(len(occ)),
        "n_occurrence_rows_mapped_to_author_id": int(len(work)),
        "n_unique_publications": int(agg["pub_id"].nunique()) if not agg.empty else 0,
        "n_unique_author_entities": int(agg["author_id"].nunique()) if not agg.empty else 0,
        "n_publication_author_entity_rows": int(len(agg)),
        "n_missing_author_id_after_merge": int(work["author_id"].isna().sum()) if "author_id" in work.columns else 0,
    })

    return agg, audit