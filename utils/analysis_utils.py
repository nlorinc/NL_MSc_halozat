"""
Meta-analízishez és nem-hálózati ábrázolásokhoz használt segédfüggvények.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def prepare_author_meta_analysis_base(
    author_nodes_export_enriched: pd.DataFrame,
) -> pd.DataFrame:
    """
    A szerző node táblából előkészíti a meta-analízishez szükséges
    szerzőszintű alapadatokat.
    """
    df = author_nodes_export_enriched.copy()

    numeric_cols = [
        "pub_count_total",
        "total_evidence",
        "citations",
        "cit_per_pub",
        "fwci",
        "h_index",
        "scholarly_output",
        "author_degree",
        "author_strength",
        "author_betweenness",
        "author_betweenness_weighted",
        "author_pagerank_weighted",
        "author_component_size",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def build_faculty_meta_summary(
    author_nodes_export_enriched: pd.DataFrame,
    faculty_nodes_export_enriched: pd.DataFrame,
    faculty_country_edges: pd.DataFrame,
) -> pd.DataFrame:
    """
    Kari meta-összesítő tábla készítése.

    A kari szintű összesítéshez:
    - a szerzők primary_kar alapján kerülnek karhoz
    - a faculty node táblából átvesszük a kari alapszámokat
    - a faculty_country_edges táblából hozzávesszük az országpartner-számokat
    """
    authors = prepare_author_meta_analysis_base(author_nodes_export_enriched)

    authors_primary = authors.loc[
        authors["primary_kar"].notna() &
        (authors["primary_kar"] != "INTER")
    ].copy()

    author_summary = (
        authors_primary.groupby("primary_kar")
        .agg(
            n_authors_primary=("author_id", "nunique"),
            pub_count_sum_authors=("pub_count_total", "sum"),
            pub_count_mean_authors=("pub_count_total", "mean"),
            pub_count_median_authors=("pub_count_total", "median"),
            citations_mean=("citations", "mean"),
            citations_median=("citations", "median"),
            cit_per_pub_mean=("cit_per_pub", "mean"),
            fwci_mean=("fwci", "mean"),
            fwci_median=("fwci", "median"),
            h_index_mean=("h_index", "mean"),
            h_index_median=("h_index", "median"),
            author_degree_mean=("author_degree", "mean"),
            author_degree_median=("author_degree", "median"),
            author_strength_mean=("author_strength", "mean"),
            author_strength_median=("author_strength", "median"),
            author_betweenness_weighted_mean=("author_betweenness_weighted", "mean"),
            author_pagerank_weighted_mean=("author_pagerank_weighted", "mean"),
        )
        .reset_index()
        .rename(columns={"primary_kar": "kar_code"})
    )

    fac_nodes_keep = [
        c for c in [
            "kar_code",
            "pub_count_total",
            "n_authors_primary_only",
            "n_authors_with_any_evidence",
            "self_loop_pub_count_raw",
            "self_loop_weight_frac",
            "faculty_degree",
            "faculty_strength_weight_frac",
            "faculty_betweenness",
            "faculty_betweenness_weighted",
            "faculty_pagerank_weighted",
            "faculty_component_size",
        ]
        if c in faculty_nodes_export_enriched.columns
    ]
    fac_nodes_min = faculty_nodes_export_enriched[fac_nodes_keep].copy()

    fce = faculty_country_edges.copy()
    fce = fce.dropna(subset=["country_code"]).copy()

    total_country_partners = (
        fce.groupby("kar_code")["country_code"]
        .nunique()
        .reset_index(name="n_country_partners")
    )

    hun_country_partners = (
        fce.loc[fce["is_hungary"] == True]
        .groupby("kar_code")["country_code"]
        .nunique()
        .reset_index(name="n_hungary_country_partners")
    )

    nonhun_country_partners = (
        fce.loc[fce["is_hungary"] == False]
        .groupby("kar_code")["country_code"]
        .nunique()
        .reset_index(name="n_nonhungary_country_partners")
    )

    summary = fac_nodes_min.merge(author_summary, on="kar_code", how="left")
    summary = summary.merge(total_country_partners, on="kar_code", how="left")
    summary = summary.merge(hun_country_partners, on="kar_code", how="left")
    summary = summary.merge(nonhun_country_partners, on="kar_code", how="left")

    fill_zero_cols = [
        "n_country_partners",
        "n_hungary_country_partners",
        "n_nonhungary_country_partners",
    ]
    for col in fill_zero_cols:
        if col in summary.columns:
            summary[col] = pd.to_numeric(summary[col], errors="coerce").fillna(0).astype(int)

    summary = summary.sort_values(
        ["pub_count_total", "kar_code"],
        ascending=[False, True],
        kind="stable"
    ).reset_index(drop=True)

    return summary

import networkx as nx


def build_author_nodes_gephi_kat(
    author_nodes_gephi: pd.DataFrame,
    author_edges_gephi: pd.DataFrame,
    min_faculty_size: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    KAT kategória hozzárendelése a szerzőkhöz.

    Első körös beállítás:
    - beágyazottsági metrika: kari indukált részgráfban számolt weighted betweenness
    - tudományos metrika: h-index

    A Q1/Q3 küszöbalapú besorolás faculty-szinten történik, a primary_kar alapján.
    Holtversenyeket együtt tartunk; ha a kari BC mindenkinél azonos, nem soroljuk be a kart.
    A végső author_nodes_gephi_KAT táblába csak egy új oszlop kerül: KAT.
    """

    nodes = author_nodes_gephi.copy()
    edges = author_edges_gephi.copy()

    # ---- oszlopnevek ----
    def pick_col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        raise KeyError(f"Nincs megfelelő oszlop a következők közül: {candidates}")

    id_col = pick_col(nodes, ["author_id", "Id"])
    kar_col = pick_col(nodes, ["primary_kar"])
    sci_col = pick_col(nodes, ["h_index"])

    source_col = pick_col(edges, ["Source", "source"])
    target_col = pick_col(edges, ["Target", "target"])
    weight_col = pick_col(edges, ["Weight", "weight"])

    nodes[id_col] = nodes[id_col].astype(str)
    edges[source_col] = edges[source_col].astype(str)
    edges[target_col] = edges[target_col].astype(str)

    # ---- teljes DE gráf felépítése ----
    G = nx.Graph()
    G.add_nodes_from(nodes[id_col].tolist())

    for _, row in edges.iterrows():
        s = row[source_col]
        t = row[target_col]
        w = pd.to_numeric(row[weight_col], errors="coerce")

        if pd.isna(s) or pd.isna(t) or pd.isna(w):
            continue
        if s == t:
            continue
        if float(w) <= 0:
            continue

        G.add_edge(s, t, weight=float(w), distance=1.0 / float(w))

    # ---- kari részgráfban számolt weighted betweenness ----
    nodes["embed_metric_local_betweenness"] = np.nan

    faculty_sizes = (
        nodes.loc[
            nodes[kar_col].notna() & (nodes[kar_col] != "INTER")
        ]
        .groupby(kar_col)[id_col]
        .nunique()
        .to_dict()
    )

    eligible_faculties = {
        kar for kar, n in faculty_sizes.items() if n >= min_faculty_size
    }

    for kar, grp in nodes.groupby(kar_col, dropna=False):
        if pd.isna(kar) or kar == "INTER":
            continue

        ids = grp[id_col].astype(str).tolist()

        # túl kicsi kar -> később nem besorolható
        if kar not in eligible_faculties:
            continue

        subg = G.subgraph(ids).copy()

        if subg.number_of_nodes() == 0:
            continue

        if subg.number_of_edges() == 0:
            btw = {n: 0.0 for n in subg.nodes()}
        else:
            btw = nx.betweenness_centrality(
                subg,
                normalized=True,
                weight="distance"
            )

        mask = nodes[id_col].isin(btw.keys())
        nodes.loc[mask, "embed_metric_local_betweenness"] = (
            nodes.loc[mask, id_col].map(btw)
        )

    # ---- csak a stabilan kategorizálható kör ----
    work = nodes.copy()

    work["kat_eligible"] = (
        work[kar_col].isin(eligible_faculties) &
        work[kar_col].notna() &
        (work[kar_col] != "INTER") &
        work["embed_metric_local_betweenness"].notna() &
        pd.to_numeric(work[sci_col], errors="coerce").notna()
    )

    work["sci_metric_h_index"] = pd.to_numeric(work[sci_col], errors="coerce")

    # ---- Kari relatív mutatók és Q1/Q3 küszöbalapú besorolás ----
    # A percentile-rangok csak diagnosztikai célúak: erős holtversenyek (BC=0)
    # esetén nem alkalmasak az alsó kvartilis lehatárolására.
    work["embed_pct"] = np.nan
    work["sci_pct"] = np.nan
    work["embed_tier"] = pd.Series(pd.NA, index=work.index, dtype="object")
    work["sci_tier"] = pd.Series(pd.NA, index=work.index, dtype="object")

    def quantile_tier(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        if values.nunique(dropna=True) < 2:
            return pd.Series("middle", index=series.index)

        q25 = values.quantile(0.25)
        q75 = values.quantile(0.75)
        # Ha Q1=Q3 (pl. sok nulla BC), csak a szigorúan magasabb
        # érték lehet felső csoport; az azonos értékeket nem bontjuk szét.
        is_top = values.ge(q75) if q75 > q25 else values.gt(q75)
        tier = np.select(
            [values.le(q25), is_top],
            ["bottom", "top"],
            default="middle",
        )
        return pd.Series(tier, index=series.index)

    for kar, grp in work.loc[work["kat_eligible"]].groupby(kar_col):
        idx = grp.index
        embed = grp["embed_metric_local_betweenness"]
        sci = grp["sci_metric_h_index"]

        # Nulla szóródásnál a kari BC nem különbözteti meg a szerzőket.
        if embed.nunique(dropna=True) < 2:
            work.loc[idx, "kat_eligible"] = False
            continue

        work.loc[idx, "embed_pct"] = embed.rank(method="average", pct=True)
        work.loc[idx, "sci_pct"] = sci.rank(method="average", pct=True)
        work.loc[idx, "embed_tier"] = quantile_tier(embed)
        work.loc[idx, "sci_tier"] = quantile_tier(sci)

    def kat_from_tiers(embed_tier, sci_tier, eligible):
        if not eligible:
            return "nem besorolható"

        if embed_tier == "top" and sci_tier == "top":
            return "vezetők"
        if embed_tier == "bottom" and sci_tier == "bottom":
            return "kezdők"
        if embed_tier == "top" and sci_tier == "bottom":
            return "integrátorok"
        if embed_tier == "bottom" and sci_tier == "top":
            return "sztárok"
        if embed_tier == "top" and sci_tier == "middle":
            return "együttműködők"
        if embed_tier == "middle" and sci_tier == "top":
            return "feltörekvők"

        return "középmezőny"

    work["KAT"] = [
        kat_from_tiers(e, s, ok)
        for e, s, ok in zip(work["embed_tier"], work["sci_tier"], work["kat_eligible"])
    ]

    # ---- végső gephi tábla: csak 1 új oszlop ----
    author_nodes_gephi_kat = author_nodes_gephi.copy()
    author_nodes_gephi_kat[id_col] = author_nodes_gephi_kat[id_col].astype(str)

    kat_map = (
        work[[id_col, "KAT"]]
        .drop_duplicates(subset=[id_col], keep="first")
        .set_index(id_col)["KAT"]
        .to_dict()
    )

    author_nodes_gephi_kat["KAT"] = author_nodes_gephi_kat[id_col].map(kat_map)

    # ---- részletes diagnosztikai tábla ----
    kat_details = work[[
        id_col,
        kar_col,
        "sci_metric_h_index",
        "embed_metric_local_betweenness",
        "embed_pct",
        "sci_pct",
        "embed_tier",
        "sci_tier",
        "kat_eligible",
        "KAT",
    ]].copy()

    # ---- kari összesítés ----
    kat_faculty_summary = (
        kat_details.groupby([kar_col, "KAT"], dropna=False)[id_col]
        .nunique()
        .reset_index(name="n_authors")
        .sort_values([kar_col, "KAT"], kind="stable")
        .reset_index(drop=True)
    )

    audit = pd.Series({
        "n_author_rows_total": int(len(author_nodes_gephi_kat)),
        "n_faculties_total": int(len(faculty_sizes)),
        "n_faculties_eligible": int(work.loc[work["kat_eligible"], kar_col].nunique()),
        "n_authors_eligible": int(work["kat_eligible"].sum()),
        "n_authors_not_eligible": int((~work["kat_eligible"]).sum()),
        "n_kat_vezetok": int((work["KAT"] == "vezetők").sum()),
        "n_kat_kezdok": int((work["KAT"] == "kezdők").sum()),
        "n_kat_integratorok": int((work["KAT"] == "integrátorok").sum()),
        "n_kat_sztarok": int((work["KAT"] == "sztárok").sum()),
        "n_kat_egyuttmukodok": int((work["KAT"] == "együttműködők").sum()),
        "n_kat_feltorekvok": int((work["KAT"] == "feltörekvők").sum()),
        "n_kat_kozepmezony": int((work["KAT"] == "középmezőny").sum()),
        "n_kat_nem_besorolhato": int((work["KAT"] == "nem besorolható").sum()),
    })

    return author_nodes_gephi_kat, kat_details, kat_faculty_summary, audit