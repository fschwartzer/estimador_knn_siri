from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd


MODULE_API_VERSION = "6.1.3"


TIPO_ITBI = "guia itbi"
TIPO_OFERTA = "oferta"
TIPO_ALUGUEL = "oferta aluguel"


@dataclass(frozen=True)
class ColumnMapping:
    tipo_informacao: str
    finalidade_oferta: str
    valor: str
    area_construida: str | None
    area_privativa: str | None
    latitude: str
    longitude: str
    siat_area_total_lote: str | None
    testada: str | None


@dataclass(frozen=True)
class PreparationResult:
    data: pd.DataFrame
    discount: float
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class EstimateResult:
    estimated_unit_value: float
    estimated_total_value: float
    weighted_std_unit: float
    effective_neighbors: float
    neighbors: pd.DataFrame
    active_features: list[str]
    geographic_scale_km: float
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class BacktestResult:
    predictions: pd.DataFrame
    metrics: dict[str, Any]
    diagnostics: dict[str, Any]


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().casefold()
    replacements = str.maketrans(
        "áàãâäéèêëíìîïóòõôöúùûüç",
        "aaaaaeeeeiiiiooooouuuuc",
    )
    return " ".join(text.translate(replacements).split())


def to_numeric(series: pd.Series) -> pd.Series:
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


def _positive_values(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr) & (arr > 0)]


def estimate_offer_discount(
    itbi_unit_values: Iterable[float],
    offer_unit_values: Iterable[float],
    cap: float = 0.20,
    offers_only_discount: float = 0.10,
) -> tuple[float, dict[str, Any]]:
    """
    Define o fator de oferta por duas regras mutuamente exclusivas:

    1. Quando existem apenas ofertas, aplica desconto convencional de 10%.
    2. Quando há pelo menos dois dados de ITBI e dois de oferta, calcula:

           mediana(1 - VU_ITBI / VU_Oferta)

       em quantis pareados, usando ``cap`` somente como teto do desconto
       empiricamente calculado.

    O desconto convencional de 10% não é produzido pela razão entre as
    distribuições e, portanto, não utiliza o teto empírico de 20%.
    """
    itbi = _positive_values(itbi_unit_values)
    offers = _positive_values(offer_unit_values)

    diagnostics: dict[str, Any] = {
        "n_itbi_discount": int(itbi.size),
        "n_offer_discount": int(offers.size),
        "discount_cap": float(cap),
        "offers_only_discount": float(offers_only_discount),
        "discount_was_capped": False,
    }

    # Regra subsidiária: a amostra contém ofertas, mas nenhuma Guia ITBI.
    if itbi.size == 0 and offers.size > 0:
        diagnostics.update(
            {
                "discount_method": "fator convencional para amostra somente de ofertas",
                "discount_source": "offers_only_fallback",
                "raw_discount_median": np.nan,
                "quantiles_used": 0,
                "discount_warning": (
                    f"A amostra contém somente ofertas. Foi aplicado o desconto "
                    f"convencional de {offers_only_discount:.0%}; o teto de "
                    f"{cap:.0%} é reservado ao desconto calculado pela razão "
                    "entre Guias ITBI e ofertas."
                ),
            }
        )
        return float(offers_only_discount), diagnostics

    # Sem ofertas, não há fator de oferta a aplicar.
    if offers.size == 0:
        diagnostics.update(
            {
                "discount_method": "sem ofertas para ajustar",
                "discount_source": "no_offers",
                "raw_discount_median": np.nan,
                "quantiles_used": 0,
            }
        )
        return 0.0, diagnostics

    # Existe algum ITBI, mas não há quantidade suficiente para quantis pareados.
    if itbi.size < 2 or offers.size < 2:
        diagnostics.update(
            {
                "discount_method": "amostra insuficiente para razão empírica",
                "discount_source": "insufficient_mixed_sample",
                "raw_discount_median": np.nan,
                "quantiles_used": 0,
                "discount_warning": (
                    "Desconto igual a zero: para calcular a razão empírica são "
                    "necessários ao menos dois dados de Guia ITBI e dois de "
                    "Oferta. O desconto convencional de 10% é aplicado somente "
                    "quando não existe nenhuma Guia ITBI."
                ),
            }
        )
        return 0.0, diagnostics

    n_quantiles = int(np.clip(min(itbi.size, offers.size), 5, 19))
    quantiles = np.linspace(0.10, 0.90, n_quantiles)
    q_itbi = np.quantile(itbi, quantiles)
    q_offer = np.quantile(offers, quantiles)

    valid = np.isfinite(q_itbi) & np.isfinite(q_offer) & (q_offer > 0)
    raw_discounts = 1.0 - (q_itbi[valid] / q_offer[valid])
    raw_discounts = raw_discounts[np.isfinite(raw_discounts)]

    if raw_discounts.size == 0:
        diagnostics.update(
            {
                "discount_method": "falha na razão empírica",
                "discount_source": "empirical_failure",
                "raw_discount_median": np.nan,
                "quantiles_used": 0,
                "discount_warning": "Não foi possível calcular o desconto.",
            }
        )
        return 0.0, diagnostics

    raw_median = float(np.median(raw_discounts))
    discount = float(np.clip(raw_median, 0.0, cap))
    diagnostics.update(
        {
            "discount_method": "mediana de descontos em quantis pareados",
            "discount_source": "empirical_ratio",
            "raw_discount_median": raw_median,
            "raw_discount_mean_diagnostic": float(np.mean(raw_discounts)),
            "quantiles_used": int(raw_discounts.size),
            "discount_was_capped": bool(raw_median > cap),
        }
    )

    if raw_median > cap:
        diagnostics["discount_warning"] = (
            f"O desconto bruto de {raw_median:.1%} foi limitado ao teto de "
            f"{cap:.0%}."
        )

    return discount, diagnostics


def _parse_registration_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    numeric = pd.to_numeric(series, errors="coerce")
    serial_mask = parsed.isna() & numeric.between(1, 100000)
    if serial_mask.any():
        parsed.loc[serial_mask] = pd.to_datetime(
            numeric.loc[serial_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )
    return parsed


def deduplicate_offers(
    data: pd.DataFrame,
    date_column: str | None,
    identifier_columns: Iterable[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "offer_deduplication_enabled": True,
        "offer_duplicates_removed": 0,
        "offer_duplicate_groups": 0,
        "offer_rows_without_identifier": 0,
        "offer_rows_without_valid_date": 0,
        "offer_deduplication_date_column": date_column or "",
        "offer_deduplication_identifier_columns": "",
    }

    identifier_columns = [
        column for column in identifier_columns if column and column in data.columns
    ]
    diagnostics["offer_deduplication_identifier_columns"] = ", ".join(
        identifier_columns
    )
    if not identifier_columns:
        diagnostics["deduplication_warning"] = (
            "A deduplicação não foi aplicada: nenhuma coluna identificadora "
            "foi encontrada."
        )
        return data, diagnostics

    offers = data.loc[data["_tipo_norm"].eq(TIPO_OFERTA)].copy()
    if offers.empty:
        return data, diagnostics

    key = pd.Series("", index=offers.index, dtype="string")
    source = pd.Series("", index=offers.index, dtype="string")
    ignored = {"", "transacao", "transação", "nan", "none", "<na>"}

    for column in identifier_columns:
        normalized = offers[column].map(normalize_text).astype("string")
        valid = ~normalized.isin(ignored)
        fill = key.eq("") & valid
        key.loc[fill] = normalize_text(column) + "::" + normalized.loc[fill]
        source.loc[fill] = column

    offers["_chave_oferta_deduplicacao"] = key
    offers["_fonte_chave_oferta"] = source
    without_id = key.eq("")
    diagnostics["offer_rows_without_identifier"] = int(without_id.sum())

    candidates = offers.loc[~without_id].copy()
    if candidates.empty:
        diagnostics["deduplication_warning"] = (
            "Os identificadores das ofertas estão vazios; nenhuma linha foi removida."
        )
        return data, diagnostics

    if date_column and date_column in candidates.columns:
        candidates["_data_registro_deduplicacao"] = _parse_registration_dates(
            candidates[date_column]
        )
    else:
        candidates["_data_registro_deduplicacao"] = pd.NaT
        diagnostics["deduplication_warning"] = (
            "A coluna de data não foi encontrada. Em empates, foi mantida a "
            "última linha do arquivo."
        )

    diagnostics["offer_rows_without_valid_date"] = int(
        candidates["_data_registro_deduplicacao"].isna().sum()
    )

    candidates = candidates.sort_values(
        [
            "_chave_oferta_deduplicacao",
            "_data_registro_deduplicacao",
            "_row_excel",
        ],
        ascending=[True, True, True],
        na_position="first",
        kind="mergesort",
    )
    group_sizes = candidates.groupby("_chave_oferta_deduplicacao").size()
    diagnostics["offer_duplicate_groups"] = int((group_sizes > 1).sum())

    duplicated = candidates.duplicated(
        subset=["_chave_oferta_deduplicacao"], keep="last"
    )
    removed_indices = candidates.index[duplicated]
    diagnostics["offer_duplicates_removed"] = int(len(removed_indices))

    cleaned = data.drop(index=removed_indices).copy()
    kept = candidates.loc[
        ~duplicated,
        [
            "_chave_oferta_deduplicacao",
            "_fonte_chave_oferta",
            "_data_registro_deduplicacao",
        ],
    ]
    for column in kept.columns:
        cleaned.loc[kept.index, column] = kept[column]
    return cleaned, diagnostics


def validate_mapping(df: pd.DataFrame, mapping: ColumnMapping) -> None:
    required = [
        mapping.tipo_informacao,
        mapping.finalidade_oferta,
        mapping.valor,
        mapping.latitude,
        mapping.longitude,
    ]
    optional = [
        mapping.area_construida,
        mapping.area_privativa,
        mapping.siat_area_total_lote,
        mapping.testada,
    ]
    missing = [column for column in required if column not in df.columns]
    missing += [
        column for column in optional if column is not None and column not in df.columns
    ]
    if missing:
        raise ValueError(
            "As seguintes colunas mapeadas não existem: "
            + ", ".join(sorted(set(missing)))
        )


def prepare_data(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    selected_purpose: str,
    value_kind: str,
    reference_area_column: str,
    discount_cap: float = 0.20,
    remove_offer_duplicates: bool = True,
    duplicate_date_column: str | None = None,
    duplicate_identifier_columns: Iterable[str] = (),
) -> PreparationResult:
    validate_mapping(df, mapping)
    if reference_area_column not in df.columns:
        raise ValueError("A coluna de área de referência não existe.")

    data = df.copy()
    data["_row_excel"] = np.arange(2, len(data) + 2)
    data["_tipo_norm"] = data[mapping.tipo_informacao].map(normalize_text)
    data["_finalidade_norm"] = data[mapping.finalidade_oferta].map(normalize_text)

    data = data.loc[
        data["_finalidade_norm"].eq(normalize_text(selected_purpose))
    ].copy()
    data = data.loc[
        data["_tipo_norm"].isin([TIPO_ITBI, TIPO_OFERTA])
    ].copy()

    dedup_diag: dict[str, Any] = {
        "offer_deduplication_enabled": bool(remove_offer_duplicates),
        "offer_duplicates_removed": 0,
        "offer_duplicate_groups": 0,
        "offer_rows_without_identifier": 0,
        "offer_rows_without_valid_date": 0,
    }
    if remove_offer_duplicates:
        data, dedup_diag = deduplicate_offers(
            data,
            duplicate_date_column,
            duplicate_identifier_columns,
        )

    numeric_columns = {
        mapping.valor,
        mapping.latitude,
        mapping.longitude,
        reference_area_column,
    }
    for column in (
        mapping.area_construida,
        mapping.area_privativa,
        mapping.siat_area_total_lote,
        mapping.testada,
    ):
        if column:
            numeric_columns.add(column)

    for column in numeric_columns:
        data[column] = to_numeric(data[column])

    value_kind_norm = normalize_text(value_kind)
    if value_kind_norm == "valor total":
        data["_valor_unitario_original"] = (
            data[mapping.valor] / data[reference_area_column]
        )
    elif value_kind_norm in {
        "valor unitario",
        "valor unitario por m2",
        "valor unitario por m²",
    }:
        data["_valor_unitario_original"] = data[mapping.valor]
    else:
        raise ValueError("Natureza do valor inválida.")

    valid = (
        np.isfinite(data["_valor_unitario_original"])
        & data["_valor_unitario_original"].gt(0)
    )
    data = data.loc[valid].copy()

    itbi = data.loc[
        data["_tipo_norm"].eq(TIPO_ITBI), "_valor_unitario_original"
    ]
    offers = data.loc[
        data["_tipo_norm"].eq(TIPO_OFERTA), "_valor_unitario_original"
    ]
    discount, discount_diag = estimate_offer_discount(itbi, offers, discount_cap)

    data["_fator_ajuste"] = np.where(
        data["_tipo_norm"].eq(TIPO_OFERTA), 1.0 - discount, 1.0
    )
    data["_valor_unitario_ajustado"] = (
        data["_valor_unitario_original"] * data["_fator_ajuste"]
    )

    diagnostics = {
        **discount_diag,
        **dedup_diag,
        "purpose": selected_purpose,
        "n_filtered": int(len(data)),
        "n_itbi": int(data["_tipo_norm"].eq(TIPO_ITBI).sum()),
        "n_offer": int(data["_tipo_norm"].eq(TIPO_OFERTA).sum()),
        "reference_area_column": reference_area_column,
        "value_kind": value_kind,
    }
    return PreparationResult(data=data, discount=discount, diagnostics=diagnostics)


def _robust_center_scale(values: np.ndarray) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 1.0
    center = float(np.median(values))
    q25, q75 = np.quantile(values, [0.25, 0.75])
    scale = float(q75 - q25)
    if not np.isfinite(scale) or scale <= 1e-12:
        mad = float(np.median(np.abs(values - center)))
        scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = float(np.std(values))
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = max(abs(center), 1.0)
    return center, scale


def _local_xy_km(
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    target_lat: float,
    target_lon: float,
) -> tuple[np.ndarray, np.ndarray]:
    radius = 6371.0088
    lat0 = np.radians(target_lat)
    x = radius * np.cos(lat0) * np.radians(longitudes - target_lon)
    y = radius * np.radians(latitudes - target_lat)
    return x, y


def _weighted_quantile(
    values: np.ndarray,
    weights: np.ndarray,
    quantile: float,
) -> float:
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    cutoff = quantile * weights.sum()
    return float(values[np.searchsorted(cumulative, cutoff, side="left")])


def _cap_and_normalize_weights(
    raw_weights: np.ndarray,
    requested_cap: float,
) -> tuple[np.ndarray, float]:
    raw = np.asarray(raw_weights, dtype=float)
    raw = np.where(np.isfinite(raw) & (raw > 0), raw, 0.0)
    n = len(raw)
    if n == 0:
        raise ValueError("Não existem pesos para normalizar.")
    if raw.sum() <= 0:
        raw = np.ones(n, dtype=float)

    # A soma dos pesos precisa alcançar 1. Com poucos vizinhos, o teto mínimo
    # matematicamente viável é 1/n.
    effective_cap = max(float(requested_cap), 1.0 / n)
    effective_cap = min(effective_cap, 1.0)

    weights = np.zeros(n, dtype=float)
    free = np.ones(n, dtype=bool)
    remaining = 1.0

    for _ in range(n + 2):
        if not free.any():
            break
        free_raw = raw[free]
        if free_raw.sum() <= 0:
            proposed = np.full(free.sum(), remaining / free.sum())
        else:
            proposed = remaining * free_raw / free_raw.sum()

        over = proposed > effective_cap + 1e-15
        free_indices = np.flatnonzero(free)
        if not over.any():
            weights[free_indices] = proposed
            remaining = 0.0
            break

        capped_indices = free_indices[over]
        weights[capped_indices] = effective_cap
        free[capped_indices] = False
        remaining = 1.0 - weights[~free].sum()

    if free.any() and remaining > 1e-12:
        free_indices = np.flatnonzero(free)
        weights[free_indices] += remaining / len(free_indices)

    weights = np.clip(weights, 0.0, effective_cap)
    weights /= weights.sum()
    return weights, effective_cap


def _robust_weighted_mean(
    values: np.ndarray,
    weights: np.ndarray,
    mad_threshold: float,
) -> tuple[float, np.ndarray, dict[str, Any]]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    median = _weighted_quantile(values, weights, 0.50)
    abs_dev = np.abs(values - median)
    mad = _weighted_quantile(abs_dev, weights, 0.50)
    robust_sigma = 1.4826 * mad

    if not np.isfinite(robust_sigma) or robust_sigma <= 1e-12:
        clipped = values.copy()
        lower = float(np.min(values))
        upper = float(np.max(values))
    else:
        lower = float(median - mad_threshold * robust_sigma)
        upper = float(median + mad_threshold * robust_sigma)
        clipped = np.clip(values, lower, upper)

    estimate = float(np.sum(weights * clipped))
    diagnostics = {
        "robust_method": "média ponderada winsorizada por MAD",
        "robust_median": float(median),
        "robust_mad": float(mad),
        "robust_sigma": float(robust_sigma),
        "robust_lower_bound": lower,
        "robust_upper_bound": upper,
        "robust_adjusted_count": int(np.sum(~np.isclose(values, clipped))),
        "robust_adjusted_weight": float(
            np.sum(weights[~np.isclose(values, clipped)])
        ),
    }
    return estimate, clipped, diagnostics


def _resolve_features(
    mapping: ColumnMapping,
    target: dict[str, float | None],
    territorial: bool,
) -> tuple[list[tuple[str, str]], bool]:
    built_valid = any(
        target.get(key) is not None
        and np.isfinite(float(target[key]))
        and float(target[key]) > 0
        for key in ("area_construida", "area_privativa")
    )
    lot_value = target.get("siat_area_total_lote")
    lot_valid = (
        lot_value is not None
        and np.isfinite(float(lot_value))
        and float(lot_value) > 0
    )
    effective_territorial = territorial or (lot_valid and not built_valid)

    pairs = [
        ("area_construida", mapping.area_construida),
        ("area_privativa", mapping.area_privativa),
    ]
    if effective_territorial:
        pairs.extend(
            [
                ("siat_area_total_lote", mapping.siat_area_total_lote),
                ("testada", mapping.testada),
            ]
        )

    active: list[tuple[str, str]] = []
    for key, column in pairs:
        value = target.get(key)
        if (
            column
            and value is not None
            and np.isfinite(float(value))
            and float(value) > 0
        ):
            active.append((key, column))

    if effective_territorial and not any(
        key == "siat_area_total_lote" for key, _ in active
    ):
        raise ValueError(
            "Para imóvel territorial, informe e mapeie a área total do lote."
        )
    if effective_territorial and not any(
        key == "testada" for key, _ in active
    ):
        raise ValueError(
            "Para imóvel territorial, informe e mapeie a TESTADA."
        )
    if not active:
        raise ValueError(
            "Informe ao menos uma característica de área válida para o avaliando."
        )
    return active, effective_territorial


def _valid_candidates(
    data: pd.DataFrame,
    mapping: ColumnMapping,
    active_features: list[tuple[str, str]],
) -> pd.DataFrame:
    result = data.copy()
    columns = [
        mapping.latitude,
        mapping.longitude,
        "_valor_unitario_ajustado",
    ] + [column for _, column in active_features]

    valid = np.ones(len(result), dtype=bool)
    for column in columns:
        result[column] = to_numeric(result[column])
        valid &= np.isfinite(result[column])

    valid &= result["_valor_unitario_ajustado"].gt(0).to_numpy()
    valid &= result[mapping.latitude].between(-90, 90).to_numpy()
    valid &= result[mapping.longitude].between(-180, 180).to_numpy()
    for _, column in active_features:
        valid &= result[column].gt(0).to_numpy()
    return result.loc[valid].copy()


def _distance_profile(
    data: pd.DataFrame,
    mapping: ColumnMapping,
    active_features: list[tuple[str, str]],
    target: dict[str, float | None],
    similarity_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    n_features = len(active_features)
    attr_sq = np.zeros(len(data), dtype=float)

    for key, column in active_features:
        values = data[column].to_numpy(dtype=float)
        center, scale = _robust_center_scale(values)
        delta = (values - float(target[key])) / scale
        attr_sq += np.square(delta) / n_features

    lat_target = float(target["latitude"])
    lon_target = float(target["longitude"])
    latitudes = data[mapping.latitude].to_numpy(dtype=float)
    longitudes = data[mapping.longitude].to_numpy(dtype=float)
    x_km, y_km = _local_xy_km(latitudes, longitudes, lat_target, lon_target)
    radial_km = np.sqrt(np.square(x_km) + np.square(y_km))

    positive = radial_km[np.isfinite(radial_km) & (radial_km > 0)]
    geo_scale = float(np.median(positive)) if positive.size else 1.0
    geo_scale = float(np.clip(geo_scale, 0.25, 20.0))

    location_weight = 1.0 - similarity_weight
    composite_sq = (
        similarity_weight * attr_sq
        + location_weight
        * (np.square(x_km / geo_scale) + np.square(y_km / geo_scale))
    )
    return np.sqrt(composite_sq), np.sqrt(attr_sq), radial_km, geo_scale


def _extrapolation_diagnostics(
    data: pd.DataFrame,
    neighbors: pd.DataFrame,
    active_features: list[tuple[str, str]],
    target: dict[str, float | None],
    geo_distances: np.ndarray,
    effective_neighbors: float,
    required_effective_neighbors: float,
    robust_adjusted_weight: float,
) -> dict[str, Any]:
    points = 0
    reasons: list[str] = []
    coverage: dict[str, dict[str, float | bool]] = {}

    for key, column in active_features:
        target_value = float(target[key])
        candidates = data[column].to_numpy(dtype=float)
        selected = neighbors[column].to_numpy(dtype=float)
        nearest_gap = float(np.min(np.abs(candidates - target_value) / target_value))
        candidate_min = float(np.min(candidates))
        candidate_max = float(np.max(candidates))
        outside = target_value < candidate_min or target_value > candidate_max

        coverage[column] = {
            "target": target_value,
            "candidate_min": candidate_min,
            "candidate_max": candidate_max,
            "selected_min": float(np.min(selected)),
            "selected_max": float(np.max(selected)),
            "nearest_relative_difference": nearest_gap,
            "outside_candidate_range": bool(outside),
        }

        if outside:
            points += 3
            reasons.append(
                f"{column}: valor do avaliando fora da faixa observada na amostra"
            )
        elif nearest_gap > 0.50:
            points += 3
            reasons.append(
                f"{column}: comparável mais próximo difere mais de 50%"
            )
        elif nearest_gap > 0.30:
            points += 2
            reasons.append(
                f"{column}: comparável mais próximo difere mais de 30%"
            )
        elif nearest_gap > 0.15:
            points += 1
            reasons.append(
                f"{column}: comparável mais próximo difere mais de 15%"
            )

    median_geo = float(np.median(geo_distances))
    max_geo = float(np.max(geo_distances))
    if median_geo > 10:
        points += 2
        reasons.append("distância geográfica mediana dos vizinhos superior a 10 km")
    elif median_geo > 5:
        points += 1
        reasons.append("distância geográfica mediana dos vizinhos superior a 5 km")

    if effective_neighbors < required_effective_neighbors:
        points += 2
        reasons.append("número efetivo de vizinhos abaixo do objetivo")

    if robust_adjusted_weight > 0.30:
        points += 1
        reasons.append("mais de 30% do peso foi afetado pelo tratamento robusto")

    if points >= 5:
        level = "alto"
    elif points >= 2:
        level = "moderado"
    else:
        level = "baixo"

    confidence = int(np.clip(100 - 12 * points, 20, 100))
    return {
        "risk_level": level,
        "risk_points": int(points),
        "confidence_score": confidence,
        "risk_reasons": reasons,
        "feature_coverage": coverage,
        "selected_geo_median_km": median_geo,
        "selected_geo_max_km": max_geo,
    }


def estimate_knn(
    preparation: PreparationResult,
    mapping: ColumnMapping,
    target: dict[str, float | None],
    reference_area_column: str,
    min_k: int = 7,
    max_k: int = 30,
    min_effective_neighbors: float = 5.0,
    similarity_weight: float = 0.75,
    distance_power: float = 1.0,
    max_individual_weight: float = 0.30,
    robust_mad_threshold: float = 2.5,
    territorial: bool = False,
    exclude_indices: Iterable[Any] = (),
) -> EstimateResult:
    if not 0.0 < similarity_weight < 1.0:
        raise ValueError("O peso físico deve estar entre 0 e 1.")
    if min_k < 2:
        raise ValueError("O k mínimo deve ser ao menos 2.")
    if max_k < min_k:
        raise ValueError("O k máximo não pode ser menor que o k mínimo.")
    if min_effective_neighbors < 1:
        raise ValueError("O mínimo de vizinhos efetivos deve ser positivo.")
    if distance_power <= 0:
        raise ValueError("A potência da distância deve ser positiva.")
    if not 0 < max_individual_weight <= 1:
        raise ValueError("O limite de peso deve estar entre 0 e 1.")
    if robust_mad_threshold <= 0:
        raise ValueError("O limiar robusto deve ser positivo.")

    active_features, effective_territorial = _resolve_features(
        mapping, target, territorial
    )
    data = _valid_candidates(preparation.data, mapping, active_features)

    exclusions = set(exclude_indices)
    if exclusions:
        data = data.loc[~data.index.isin(exclusions)].copy()
    if len(data) < 2:
        raise ValueError("Não existem candidatos suficientes para a estimativa.")

    distances, attr_dist, geo_dist, geo_scale = _distance_profile(
        data, mapping, active_features, target, similarity_weight
    )
    order = np.argsort(distances, kind="mergesort")
    max_available = min(int(max_k), len(data))
    min_available = min(max(int(min_k), 2), max_available)

    selected_k = max_available
    selected_weights: np.ndarray | None = None
    selected_effective = 0.0
    selected_cap = max_individual_weight

    epsilon = 1e-9
    for candidate_k in range(min_available, max_available + 1):
        idx = order[:candidate_k]
        raw = 1.0 / np.power(distances[idx] + epsilon, distance_power)
        weights, effective_cap = _cap_and_normalize_weights(
            raw, max_individual_weight
        )
        effective_n = float(1.0 / np.sum(np.square(weights)))
        selected_k = candidate_k
        selected_weights = weights
        selected_effective = effective_n
        selected_cap = effective_cap
        if effective_n >= min_effective_neighbors:
            break

    if selected_weights is None:
        raise RuntimeError("Falha na seleção adaptativa de vizinhos.")

    selected_positions = order[:selected_k]
    neighbors = data.iloc[selected_positions].copy()
    selected_distances = distances[selected_positions]
    selected_attr = attr_dist[selected_positions]
    selected_geo = geo_dist[selected_positions]

    values = neighbors["_valor_unitario_ajustado"].to_numpy(dtype=float)
    estimated_unit, robust_values, robust_diag = _robust_weighted_mean(
        values, selected_weights, robust_mad_threshold
    )

    mapping_to_target = {
        mapping.area_construida: "area_construida",
        mapping.area_privativa: "area_privativa",
        mapping.siat_area_total_lote: "siat_area_total_lote",
    }
    reference_target = target.get(reference_area_column)
    if reference_target is None:
        reference_key = mapping_to_target.get(reference_area_column)
        reference_target = target.get(reference_key) if reference_key else None
    if (
        reference_target is None
        or not np.isfinite(float(reference_target))
        or float(reference_target) <= 0
    ):
        raise ValueError(
            "Informe a área do avaliando correspondente à área de referência."
        )

    estimated_total = estimated_unit * float(reference_target)
    weighted_variance = float(
        np.sum(selected_weights * np.square(robust_values - estimated_unit))
    )
    weighted_std = float(np.sqrt(max(weighted_variance, 0.0)))

    neighbors["_distancia_caracteristicas"] = selected_attr
    neighbors["_distancia_geografica_km"] = selected_geo
    neighbors["_distancia_composta"] = selected_distances
    neighbors["_peso_knn"] = selected_weights
    neighbors["_valor_unitario_robusto"] = robust_values
    neighbors["_ajuste_robusto"] = values - robust_values
    neighbors["_contribuicao_valor_unitario"] = (
        selected_weights * robust_values
    )

    extrapolation = _extrapolation_diagnostics(
        data,
        neighbors,
        active_features,
        target,
        selected_geo,
        selected_effective,
        min_effective_neighbors,
        float(robust_diag["robust_adjusted_weight"]),
    )

    diagnostics = {
        "k_min_requested": int(min_k),
        "k_max_requested": int(max_k),
        "k_used": int(selected_k),
        "adaptive_k_reached_target": bool(
            selected_effective >= min_effective_neighbors
        ),
        "min_effective_neighbors": float(min_effective_neighbors),
        "effective_neighbors": float(selected_effective),
        "max_individual_weight_requested": float(max_individual_weight),
        "max_individual_weight_effective": float(selected_cap),
        "max_weight_observed": float(np.max(selected_weights)),
        "similarity_weight": float(similarity_weight),
        "location_weight": float(1.0 - similarity_weight),
        "distance_power": float(distance_power),
        "n_candidates": int(len(data)),
        "reference_target_area": float(reference_target),
        "effective_territorial": bool(effective_territorial),
        **robust_diag,
        **extrapolation,
    }

    return EstimateResult(
        estimated_unit_value=estimated_unit,
        estimated_total_value=estimated_total,
        weighted_std_unit=weighted_std,
        effective_neighbors=selected_effective,
        neighbors=neighbors,
        active_features=[column for _, column in active_features],
        geographic_scale_km=geo_scale,
        diagnostics=diagnostics,
    )


def _safe_group_value(value: Any) -> str:
    normalized = normalize_text(value)
    return "" if normalized in {"", "nan", "none", "<na>"} else normalized


def backtest_knn(
    preparation: PreparationResult,
    mapping: ColumnMapping,
    reference_area_column: str,
    territorial: bool,
    min_k: int,
    max_k: int,
    min_effective_neighbors: float,
    similarity_weight: float,
    distance_power: float,
    max_individual_weight: float,
    robust_mad_threshold: float,
    sample_size: int = 150,
    group_column: str | None = None,
    evaluation_scope: str = "itbi",
    random_state: int = 42,
) -> BacktestResult:
    data = preparation.data.copy()
    if normalize_text(evaluation_scope) in {"itbi", "guias itbi", "guia itbi"}:
        eligible = data.loc[data["_tipo_norm"].eq(TIPO_ITBI)].copy()
        scope_label = "Guias ITBI"
    else:
        eligible = data.copy()
        scope_label = "Todos os dados ajustados"

    required = [
        mapping.latitude,
        mapping.longitude,
        "_valor_unitario_ajustado",
        reference_area_column,
    ]
    if territorial:
        if not mapping.testada:
            raise ValueError(
                "O backtesting territorial exige uma coluna de TESTADA mapeada."
            )
        required.append(mapping.testada)
    for column in required:
        eligible[column] = to_numeric(eligible[column])
    valid = np.ones(len(eligible), dtype=bool)
    for column in required:
        valid &= np.isfinite(eligible[column])
    valid &= eligible["_valor_unitario_ajustado"].gt(0).to_numpy()
    valid &= eligible[reference_area_column].gt(0).to_numpy()
    valid &= eligible[mapping.latitude].between(-90, 90).to_numpy()
    valid &= eligible[mapping.longitude].between(-180, 180).to_numpy()
    eligible = eligible.loc[valid].copy()

    if len(eligible) < 10:
        raise ValueError(
            "O backtesting exige pelo menos 10 observações válidas no conjunto escolhido."
        )

    n_sample = min(max(int(sample_size), 10), len(eligible))
    sampled = eligible.sample(n=n_sample, random_state=random_state)

    group_series = None
    if group_column and group_column in data.columns:
        group_series = data[group_column].map(_safe_group_value)

    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for index, row in sampled.iterrows():
        target = {
            "area_construida": (
                float(row[mapping.area_construida])
                if mapping.area_construida
                and pd.notna(row.get(mapping.area_construida))
                and float(row[mapping.area_construida]) > 0
                else None
            ),
            "area_privativa": (
                float(row[mapping.area_privativa])
                if mapping.area_privativa
                and pd.notna(row.get(mapping.area_privativa))
                and float(row[mapping.area_privativa]) > 0
                else None
            ),
            "siat_area_total_lote": (
                float(row[mapping.siat_area_total_lote])
                if mapping.siat_area_total_lote
                and pd.notna(row.get(mapping.siat_area_total_lote))
                and float(row[mapping.siat_area_total_lote]) > 0
                else None
            ),
            "testada": (
                float(row[mapping.testada])
                if mapping.testada
                and pd.notna(row.get(mapping.testada))
                and float(row[mapping.testada]) > 0
                else None
            ),
            "latitude": float(row[mapping.latitude]),
            "longitude": float(row[mapping.longitude]),
        }

        reference_key_map = {
            mapping.area_construida: "area_construida",
            mapping.area_privativa: "area_privativa",
            mapping.siat_area_total_lote: "siat_area_total_lote",
        }
        key = reference_key_map.get(reference_area_column)
        if key:
            target[reference_area_column] = target[key]

        exclusions: set[Any] = {index}
        group_value = ""
        if group_series is not None:
            group_value = group_series.loc[index]
            if group_value:
                exclusions.update(group_series.index[group_series.eq(group_value)])

        try:
            estimate = estimate_knn(
                preparation=preparation,
                mapping=mapping,
                target=target,
                reference_area_column=reference_area_column,
                min_k=min_k,
                max_k=max_k,
                min_effective_neighbors=min_effective_neighbors,
                similarity_weight=similarity_weight,
                distance_power=distance_power,
                max_individual_weight=max_individual_weight,
                robust_mad_threshold=robust_mad_threshold,
                territorial=territorial,
                exclude_indices=exclusions,
            )
        except Exception as exc:
            failures.append(str(exc))
            continue

        actual = float(row["_valor_unitario_ajustado"])
        predicted = float(estimate.estimated_unit_value)
        error = predicted - actual
        ape = abs(error) / actual
        records.append(
            {
                "indice_original": index,
                "linha_excel": row.get("_row_excel"),
                "grupo_excluido": group_value,
                "tipo_informacao": row.get(mapping.tipo_informacao),
                "valor_unitario_real": actual,
                "valor_unitario_estimado": predicted,
                "erro_unitario": error,
                "erro_percentual": error / actual,
                "erro_percentual_absoluto": ape,
                "k_utilizado": estimate.diagnostics["k_used"],
                "vizinhos_efetivos": estimate.effective_neighbors,
                "peso_maximo": estimate.diagnostics["max_weight_observed"],
                "risco_extrapolacao": estimate.diagnostics["risk_level"],
                "confianca": estimate.diagnostics["confidence_score"],
            }
        )

    predictions = pd.DataFrame(records)
    if len(predictions) < 5:
        detail = failures[0] if failures else "sem detalhe adicional"
        raise ValueError(
            "O backtesting produziu menos de cinco previsões válidas. "
            f"Primeiro erro: {detail}"
        )

    actual = predictions["valor_unitario_real"].to_numpy(dtype=float)
    predicted = predictions["valor_unitario_estimado"].to_numpy(dtype=float)
    errors = predicted - actual
    ape = np.abs(errors) / actual
    ratios = predicted / actual

    ss_res = float(np.sum(np.square(errors)))
    ss_tot = float(np.sum(np.square(actual - np.mean(actual))))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan

    median_ratio = float(np.median(ratios))
    cod = (
        float(np.mean(np.abs(ratios - median_ratio)) / median_ratio * 100)
        if median_ratio > 0
        else np.nan
    )
    weighted_mean_ratio = float(np.sum(predicted) / np.sum(actual))
    prd = (
        float(np.mean(ratios) / weighted_mean_ratio)
        if weighted_mean_ratio > 0
        else np.nan
    )

    metrics = {
        "n_tested": int(len(predictions)),
        "n_failed": int(n_sample - len(predictions)),
        "mae_unit": float(np.mean(np.abs(errors))),
        "medae_unit": float(np.median(np.abs(errors))),
        "rmse_unit": float(np.sqrt(np.mean(np.square(errors)))),
        "mdape": float(np.median(ape)),
        "mape": float(np.mean(ape)),
        "p90_ape": float(np.quantile(ape, 0.90)),
        "median_bias": float(np.median(errors / actual)),
        "r2": r2,
        "cod": cod,
        "prd": prd,
        "median_ratio": median_ratio,
    }
    diagnostics = {
        "evaluation_scope": scope_label,
        "sample_requested": int(sample_size),
        "sample_used": int(n_sample),
        "group_column": group_column or "",
        "random_state": int(random_state),
        "failure_examples": failures[:5],
    }
    return BacktestResult(
        predictions=predictions,
        metrics=metrics,
        diagnostics=diagnostics,
    )
