from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


MODULE_API_VERSION = "6.4.0"


DERIVED_AREA_LOTE = "__area_total_lote_efetiva"
DERIVED_AREA_CONSTRUIDA = "__area_construida_efetiva"
DERIVED_AREA_PRIVATIVA = "__area_privativa_efetiva"
DERIVED_TESTADA = "__testada_efetiva"


@dataclass(frozen=True)
class SchemaInfo:
    siri_detected: bool
    added_columns: tuple[str, ...]
    notes: tuple[str, ...]


def _normalize(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().casefold()
    replacements = str.maketrans(
        "áàãâäéèêëíìîïóòõôöúùûüç",
        "aaaaaeeeeiiiiooooouuuuc",
    )
    return " ".join(text.translate(replacements).split())


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {_normalize(column): column for column in columns}
    for candidate in candidates:
        match = lookup.get(_normalize(candidate))
        if match is not None:
            return match
    return None


def _numeric(df: pd.DataFrame, column: str | None) -> pd.Series:
    if not column or column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    series = df[column]
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = (
        series.astype("string")
        .str.strip()
        .str.replace(r"[Rr]\$", "", regex=True)
        .str.replace(r"\s+", "", regex=True)
    )
    has_comma = cleaned.str.contains(",", regex=False, na=False)
    has_dot = cleaned.str.contains(".", regex=False, na=False)
    both = has_comma & has_dot
    cleaned.loc[both] = (
        cleaned.loc[both]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    cleaned.loc[has_comma & ~has_dot] = cleaned.loc[
        has_comma & ~has_dot
    ].str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _coalesce_positive(df: pd.DataFrame, columns: Iterable[str | None]) -> pd.Series:
    result = pd.Series(np.nan, index=df.index, dtype=float)
    for column in columns:
        values = _numeric(df, column)
        values = values.where(np.isfinite(values) & (values > 0))
        result = result.where(result.notna(), values)
    return result


def _combine_by_information_type(
    df: pd.DataFrame,
    type_column: str | None,
    offer_columns: Iterable[str | None],
    itbi_columns: Iterable[str | None],
    fallback_columns: Iterable[str | None],
) -> pd.Series:
    fallback = _coalesce_positive(df, fallback_columns)
    if not type_column or type_column not in df.columns:
        return fallback

    type_norm = df[type_column].map(_normalize)
    offer_mask = type_norm.isin({"oferta", "oferta aluguel"})
    itbi_mask = type_norm.eq("guia itbi")

    result = fallback.copy()
    offer_values = _coalesce_positive(df, offer_columns)
    itbi_values = _coalesce_positive(df, itbi_columns)
    result.loc[offer_mask] = offer_values.loc[offer_mask]
    result.loc[itbi_mask] = itbi_values.loc[itbi_mask]
    return result


def enrich_known_schemas(df: pd.DataFrame) -> tuple[pd.DataFrame, SchemaInfo]:
    """Cria colunas efetivas sem alterar as colunas originais do arquivo."""
    data = df.copy()
    columns = [str(column) for column in data.columns]
    data.columns = columns

    type_column = first_existing(columns, ["tipo_informacao", "tipo_informação"])

    siri_markers = {
        "tipo_informacao",
        "siat_finalidade_descricao",
        "valor_oferta",
        "siat_latitude",
        "siat_longitude",
    }
    siri_detected = siri_markers.issubset(set(columns))

    added: list[str] = []
    notes: list[str] = []

    lot_series = _combine_by_information_type(
        data,
        type_column,
        offer_columns=["crawler_area_terreno", "siat_area_terreno"],
        itbi_columns=["siat_area_terreno", "crawler_area_terreno"],
        fallback_columns=[
            "siat_area_total_lote",
            "area_total_lote",
            "siat_area_terreno",
            "crawler_area_terreno",
        ],
    )
    if lot_series.notna().any():
        data[DERIVED_AREA_LOTE] = lot_series
        added.append(DERIVED_AREA_LOTE)
        notes.append(
            "Área do lote combinada: prioriza a área anunciada nas ofertas e "
            "a área SIAT nas Guias ITBI."
        )

    built_series = _combine_by_information_type(
        data,
        type_column,
        offer_columns=[
            "crawler_area_construida",
            "area_construida",
            "siat_area_construida",
            "itbacotot",
        ],
        itbi_columns=[
            "itbacotot",
            "area_construida",
            "siat_area_construida",
            "crawler_area_construida",
        ],
        fallback_columns=[
            "area_construida",
            "crawler_area_construida",
            "siat_area_construida",
            "itbacotot",
        ],
    )
    if built_series.notna().any():
        data[DERIVED_AREA_CONSTRUIDA] = built_series
        added.append(DERIVED_AREA_CONSTRUIDA)
        notes.append(
            "Área construída combinada conforme a origem do registro."
        )

    private_series = _combine_by_information_type(
        data,
        type_column,
        offer_columns=["crawler_area_privativa", "area_privativa", "itbacopriv"],
        itbi_columns=["itbacopriv", "area_privativa", "crawler_area_privativa"],
        fallback_columns=["area_privativa", "crawler_area_privativa", "itbacopriv"],
    )
    if private_series.notna().any():
        data[DERIVED_AREA_PRIVATIVA] = private_series
        added.append(DERIVED_AREA_PRIVATIVA)
        notes.append(
            "Área privativa combinada conforme a origem do registro."
        )

    frontage_series = _combine_by_information_type(
        data,
        type_column,
        offer_columns=[
            "anuncio_testada",
            "siat_testada_terreno",
            "testada",
            "testada_terreno",
        ],
        itbi_columns=[
            "siat_testada_terreno",
            "testada",
            "testada_terreno",
            "anuncio_testada",
        ],
        fallback_columns=[
            "testada",
            "testada_terreno",
            "siat_testada_terreno",
            "anuncio_testada",
        ],
    )
    if frontage_series.notna().any():
        data[DERIVED_TESTADA] = frontage_series
        added.append(DERIVED_TESTADA)
        notes.append(
            "Testada combinada: prioriza a testada do anúncio nas ofertas e "
            "a testada SIAT nas Guias ITBI."
        )

    return data, SchemaInfo(
        siri_detected=siri_detected,
        added_columns=tuple(added),
        notes=tuple(notes),
    )


def friendly_column_name(column: str) -> str:
    labels = {
        DERIVED_AREA_LOTE: "Área total do lote — combinada automaticamente",
        DERIVED_AREA_CONSTRUIDA: "Área construída — combinada automaticamente",
        DERIVED_AREA_PRIVATIVA: "Área privativa — combinada automaticamente",
        DERIVED_TESTADA: "Testada — combinada automaticamente",
    }
    return labels.get(column, column)
