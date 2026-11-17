"""
Sztring- és mezőnormalizáló segédfüggvények.
"""

from __future__ import annotations

import re
import numpy as np
import pandas as pd


DOI_PREFIX_PATTERN = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
    flags=re.IGNORECASE
)


def normalize_text_token(value) -> str | float:
    """
    Egyszerű szöveges normalizálás:
    - stringgé alakítás
    - szélső whitespace levágása
    - üres / nan jellegű értékek NaN-ra alakítása
    """
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    if text == "":
        return np.nan

    if text.lower() in {"nan", "none", "null"}:
        return np.nan

    return text


def normalize_doi(value) -> str | float:
    """
    DOI normalizálás:
    - whitespace levágása
    - DOI URL prefix eltávolítása
    - 'doi:' prefix eltávolítása
    - kisbetűsítés
    - placeholder értékek hiányzóvá alakítása
    - csak DOI-szerű mintát fogad el: tartalmazza a '10.' kezdetet és egy '/' jelet
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = DOI_PREFIX_PATTERN.sub("", text)
    text = text.strip().lower()

    if text in {"", "-", "--", "---", "n/a", "na", "none", "null"}:
        return np.nan

    if not text.startswith("10."):
        return np.nan

    if "/" not in text:
        return np.nan

    return text


def normalize_doi_series(series: pd.Series) -> pd.Series:
    """
    DOI-oszlop vektoros normalizálása.
    """
    return series.map(normalize_doi)


def split_scopus_multivalue(value) -> list[str]:
    """
    Scopus multiértékes mezők szétszedése.
    A tipikus elválasztó a pipe karakter, körülötte opcionális szóközökkel.
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return []

    parts = re.split(r"\s*\|\s*", text)
    parts = [p.strip() for p in parts if p.strip() != ""]

    return parts


def normalize_author_name(value) -> str | float:
    """
    Szerzőnév egyszerű tisztítása.
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = re.sub(r"\s+", " ", text).strip()

    if text == "":
        return np.nan

    return text


def normalize_scopus_author_id(value) -> str | float:
    """
    Scopus Author ID tisztítása sztringgé.
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = str(text).strip()
    text = re.sub(r"\.0$", "", text)

    if text == "":
        return np.nan

    return text


def pair_authors_and_ids(authors_value, author_ids_value) -> tuple[list[dict], bool]:
    """
    Az Authors és Scopus Author Ids mezők párosítása.

    Visszaad:
    - listát a párokról
    - bool értéket, ami jelzi, hogy a két lista hossza egyezett-e
    """
    author_names = [normalize_author_name(x) for x in split_scopus_multivalue(authors_value)]
    author_ids = [normalize_scopus_author_id(x) for x in split_scopus_multivalue(author_ids_value)]

    n_names = len(author_names)
    n_ids = len(author_ids)
    n = max(n_names, n_ids)

    pairs = []

    for i in range(n):
        name_i = author_names[i] if i < n_names else np.nan
        id_i = author_ids[i] if i < n_ids else np.nan

        if pd.isna(name_i) and pd.isna(id_i):
            continue

        pairs.append({
            "author_position": i + 1,
            "author_name_raw": name_i,
            "scopus_author_id": id_i,
        })

    lengths_match = (n_names == n_ids)

    return pairs, lengths_match


def normalize_eid(value) -> str | float:
    """
    EID tisztítása sztringgé.
    """
    text = normalize_text_token(value)

    if pd.isna(text):
        return np.nan

    text = str(text).strip()

    if text == "":
        return np.nan

    return text