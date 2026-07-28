from __future__ import annotations

from io import BytesIO
import hashlib

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


APP_NAME = "estimador_knn_siri"
APP_EDITION = "LITE 1.5"
CORE_VERSION = "6.1.3"

# Parâmetros internos: não ficam expostos ao usuário da edição LITE.
MIN_K = 7
MAX_K = 30
MIN_EFFECTIVE_NEIGHBORS = 5.0
SIMILARITY_WEIGHT = 0.75
DISTANCE_POWER = 1.0
MAX_INDIVIDUAL_WEIGHT = 0.30
ROBUST_MAD_THRESHOLD = 2.5
DISCOUNT_CAP = 0.20


st.set_page_config(
    page_title="Estimador KNN SIRI",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    import knn_valuation as _knn
    import schema_utils as _schema
except Exception as exc:
    st.error(
        "Os arquivos internos do aplicativo não puderam ser carregados. "
        "Publique app.py, knn_valuation.py e schema_utils.py juntos."
    )
    st.code(f"{type(exc).__name__}: {exc}")
    st.stop()

_required_knn = {
    "ColumnMapping",
    "EstimateResult",
    "PreparationResult",
    "estimate_knn",
    "normalize_text",
    "prepare_data",
}
_required_schema = {
    "DERIVED_AREA_CONSTRUIDA",
    "DERIVED_AREA_LOTE",
    "DERIVED_AREA_PRIVATIVA",
    "DERIVED_TESTADA",
    "enrich_known_schemas",
    "first_existing",
    "friendly_column_name",
}

_missing_knn = sorted(name for name in _required_knn if not hasattr(_knn, name))
_missing_schema = sorted(
    name for name in _required_schema if not hasattr(_schema, name)
)
_knn_version = getattr(_knn, "MODULE_API_VERSION", "anterior")
_schema_version = getattr(_schema, "MODULE_API_VERSION", "anterior")

if (
    _missing_knn
    or _missing_schema
    or _knn_version != CORE_VERSION
    or _schema_version != CORE_VERSION
):
    st.error("Os arquivos publicados pertencem a versões diferentes.")
    st.code(
        "\n".join(
            [
                f"knn_valuation.py: {_knn_version}",
                f"schema_utils.py: {_schema_version}",
                "Itens ausentes no KNN: "
                + (", ".join(_missing_knn) if _missing_knn else "nenhum"),
                "Itens ausentes no schema: "
                + (", ".join(_missing_schema) if _missing_schema else "nenhum"),
            ]
        )
    )
    st.stop()

ColumnMapping = _knn.ColumnMapping
EstimateResult = _knn.EstimateResult
PreparationResult = _knn.PreparationResult
estimate_knn = _knn.estimate_knn
normalize_text = _knn.normalize_text
prepare_data = _knn.prepare_data

DERIVED_AREA_CONSTRUIDA = _schema.DERIVED_AREA_CONSTRUIDA
DERIVED_AREA_LOTE = _schema.DERIVED_AREA_LOTE
DERIVED_AREA_PRIVATIVA = _schema.DERIVED_AREA_PRIVATIVA
DERIVED_TESTADA = _schema.DERIVED_TESTADA
enrich_known_schemas = _schema.enrich_known_schemas
first_existing = _schema.first_existing
friendly_column_name = _schema.friendly_column_name


CUSTOM_CSS = """
<style>
:root {
    --ink: #172033;
    --muted: #667085;
    --line: #E4E9F0;
    --canvas: #F6F8FA;
    --navy: #173B57;
    --teal: #0E7C7B;
    --soft-teal: #E9F5F4;
    --soft-blue: #EEF4F8;
    --amber: #A15C00;
    --red: #B42318;
}
.stApp {
    background:
        radial-gradient(circle at 92% 4%, rgba(14,124,123,.09), transparent 23rem),
        var(--canvas);
    color: var(--ink);
}
.block-container {
    max-width: 1220px;
    padding-top: 1.65rem;
    padding-bottom: 4rem;
}
.hero {
    position: relative;
    overflow: hidden;
    padding: 2rem 2.2rem;
    border: 1px solid rgba(23,59,87,.12);
    border-radius: 24px;
    background: linear-gradient(135deg, #FFFFFF 0%, #EDF7F6 100%);
    box-shadow: 0 18px 45px rgba(23,59,87,.075);
    margin-bottom: 1.25rem;
}
.hero:after {
    content: "";
    position: absolute;
    width: 280px;
    height: 280px;
    right: -100px;
    top: -145px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(14,124,123,.18), rgba(23,59,87,.02));
}
.badge {
    display: inline-flex;
    padding: .32rem .68rem;
    border-radius: 999px;
    background: rgba(14,124,123,.10);
    color: #096968;
    font-size: .74rem;
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
}
.hero h1 {
    max-width: 820px;
    margin: .82rem 0 .65rem;
    font-size: clamp(2rem, 4vw, 3.15rem);
    line-height: 1.03;
    letter-spacing: -.045em;
    color: var(--ink);
}
.hero p {
    max-width: 820px;
    margin: 0;
    color: var(--muted);
    line-height: 1.65;
    font-size: 1.01rem;
}
.step {
    display: flex;
    align-items: center;
    gap: .65rem;
    margin: 1.25rem 0 .65rem;
}
.step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.85rem;
    height: 1.85rem;
    border-radius: 50%;
    background: var(--navy);
    color: #fff;
    font-weight: 800;
    font-size: .86rem;
}
.step-title {
    font-size: 1.16rem;
    font-weight: 800;
    letter-spacing: -.015em;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--line) !important;
    border-radius: 18px !important;
    background: rgba(255,255,255,.88);
    box-shadow: 0 10px 28px rgba(23,59,87,.035);
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,.95);
    border: 1px solid var(--line);
    padding: 1rem 1.05rem;
    border-radius: 16px;
    box-shadow: 0 8px 22px rgba(23,59,87,.04);
}
[data-testid="stMetricLabel"] {
    color: var(--muted);
}
[data-testid="stMetricValue"] {
    color: var(--ink);
    letter-spacing: -.03em;
}
.stButton > button, .stDownloadButton > button {
    min-height: 2.9rem;
    border-radius: 12px;
    border: 0;
    font-weight: 800;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--navy), var(--teal));
    box-shadow: 0 10px 22px rgba(14,124,123,.18);
}
.stTabs [data-baseweb="tab-list"] {
    gap: .4rem;
    padding: .35rem;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(255,255,255,.75);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: .45rem .9rem;
}
.stTabs [aria-selected="true"] {
    color: var(--teal);
    background: var(--soft-teal);
}
.risk-card {
    min-height: 132px;
    padding: 1rem 1.1rem;
    border: 1px solid var(--line);
    border-left-width: 5px;
    border-radius: 16px;
    background: #fff;
}
.risk-card.low { border-left-color: var(--teal); }
.risk-card.moderate { border-left-color: #D97706; }
.risk-card.high { border-left-color: var(--red); }
.risk-label {
    color: var(--muted);
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .05em;
    text-transform: uppercase;
}
.risk-value {
    margin: .25rem 0;
    color: var(--ink);
    font-size: 1.45rem;
    font-weight: 850;
}
.risk-text {
    color: var(--muted);
    font-size: .88rem;
    line-height: 1.45;
}
.helper {
    padding: .85rem 1rem;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(238,244,248,.75);
    color: var(--muted);
    font-size: .9rem;
    line-height: 1.5;
}
.small-note {
    color: var(--muted);
    font-size: .84rem;
}
div[data-testid="stDataFrame"] {
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 14px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def money_br(value: float, decimals: int = 2) -> str:
    if not np.isfinite(value):
        return "—"
    text = f"{value:,.{decimals}f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def number_br(value: float, decimals: int = 2) -> str:
    if not np.isfinite(value):
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def percent_br(value: float, decimals: int = 1) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{value * 100:.{decimals}f}%".replace(".", ",")


def step_header(number: int, title: str) -> None:
    st.markdown(
        f"""
        <div class="step">
            <span class="step-number">{number}</span>
            <span class="step-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def purpose_suggests_territorial(purpose: str) -> bool:
    normalized = normalize_text(purpose)
    return any(
        term in normalized
        for term in (
            "terreno",
            "gleba",
            "lote",
            "sitio",
            "fazenda",
            "area rural",
            "chacara",
        )
    )


def choose_existing(columns: list[str], candidates: list[str]) -> str | None:
    return first_existing(columns, candidates)


def build_mapping(df: pd.DataFrame) -> tuple[ColumnMapping | None, list[str]]:
    columns = [str(column) for column in df.columns]

    tipo = choose_existing(
        columns,
        ["tipo_informacao", "tipo_informação"],
    )
    finalidade = choose_existing(
        columns,
        [
            "siat_finalidade_descricao",
            "finalidade_oferta",
            "finalidade",
            "tipo_imovel",
        ],
    )
    valor = choose_existing(
        columns,
        [
            "valor_oferta",
            "valor",
            "valor_total",
            "preco",
            "preço",
            "valor_unitario",
            "valor_unitário",
        ],
    )
    latitude = choose_existing(columns, ["siat_latitude", "latitude", "lat"])
    longitude = choose_existing(
        columns,
        ["siat_longitude", "longitude", "lon", "lng"],
    )

    area_lote = (
        DERIVED_AREA_LOTE
        if DERIVED_AREA_LOTE in columns
        else choose_existing(
            columns,
            [
                "siat_area_total_lote",
                "siat_area_terreno",
                "crawler_area_terreno",
                "area_total_lote",
            ],
        )
    )
    area_construida = (
        DERIVED_AREA_CONSTRUIDA
        if DERIVED_AREA_CONSTRUIDA in columns
        else choose_existing(
            columns,
            [
                "area_construida",
                "crawler_area_construida",
                "siat_area_construida",
                "itbacotot",
            ],
        )
    )
    area_privativa = (
        DERIVED_AREA_PRIVATIVA
        if DERIVED_AREA_PRIVATIVA in columns
        else choose_existing(
            columns,
            [
                "area_privativa",
                "crawler_area_privativa",
                "itbacopriv",
            ],
        )
    )
    testada = (
        DERIVED_TESTADA
        if DERIVED_TESTADA in columns
        else choose_existing(
            columns,
            [
                "testada",
                "testada_terreno",
                "siat_testada_terreno",
                "anuncio_testada",
            ],
        )
    )

    required = {
        "tipo de informação": tipo,
        "finalidade": finalidade,
        "valor": valor,
        "latitude": latitude,
        "longitude": longitude,
    }
    missing = [label for label, column in required.items() if not column]
    if missing:
        return None, missing

    mapping = ColumnMapping(
        tipo_informacao=tipo,
        finalidade_oferta=finalidade,
        valor=valor,
        area_construida=area_construida,
        area_privativa=area_privativa,
        latitude=latitude,
        longitude=longitude,
        siat_area_total_lote=area_lote,
        testada=testada,
    )
    return mapping, []


def detect_value_kind(value_column: str) -> str:
    normalized = normalize_text(value_column)
    if "unitario" in normalized or "unitário" in normalized:
        return "Valor unitário por m²"
    return "Valor total"



def classify_discount_alert(
    applied_discount: float,
    raw_discount: float | None,
    discount_source: str,
) -> dict[str, str]:
    """
    Classifica somente a comunicação do desconto, sem alterar o cálculo.
    """
    applied = float(applied_discount)
    raw = (
        float(raw_discount)
        if raw_discount is not None and np.isfinite(float(raw_discount))
        else np.nan
    )

    if discount_source == "offers_only_fallback":
        return {
            "level": "info",
            "title": "Fator convencional aplicado",
            "message": (
                "A amostra contém somente ofertas. Foi aplicado desconto de "
                f"{percent_br(applied)}. O teto de 20% não foi acionado, pois "
                "ele funciona exclusivamente como freio da razão empírica entre "
                "Guias ITBI e ofertas."
            ),
            "band": "10% convencional — somente ofertas",
        }

    if discount_source == "no_offers":
        return {
            "level": "success",
            "title": "Sem ofertas para ajustar",
            "message": (
                "A amostra efetiva não contém ofertas; nenhuma redução foi aplicada."
            ),
            "band": "sem ofertas",
        }

    if discount_source in {"insufficient_mixed_sample", "empirical_failure"}:
        return {
            "level": "warning",
            "title": "Razão empírica não calculada",
            "message": (
                "Existem Guias ITBI e ofertas, mas a composição não permite "
                "calcular adequadamente os quantis pareados. O desconto permaneceu "
                "em zero; o fator convencional de 10% é reservado à situação em "
                "que a amostra contém somente ofertas."
            ),
            "band": "amostra mista insuficiente",
        }

    if np.isfinite(raw) and raw > 0.20:
        return {
            "level": "error",
            "title": "Razão empírica acima do freio",
            "message": (
                f"A mediana calculada foi de {percent_br(raw)}. O freio de 20% "
                f"limitou o desconto aplicado a {percent_br(applied)}. Revise a "
                "homogeneidade entre Guias ITBI e ofertas."
            ),
            "band": "razão empírica acima de 20%",
        }

    if applied > 0.15:
        return {
            "level": "warning",
            "title": "Elasticidade elevada",
            "message": (
                f"O desconto empírico de {percent_br(applied)} está na faixa "
                "acima de 15% até 20%."
            ),
            "band": "acima de 15% até 20%",
        }

    if applied > 0.10:
        return {
            "level": "info",
            "title": "Elasticidade relevante",
            "message": (
                f"O desconto empírico de {percent_br(applied)} está na faixa "
                "acima de 10% até 15%."
            ),
            "band": "acima de 10% até 15%",
        }

    if applied > 0:
        return {
            "level": "success",
            "title": "Elasticidade usual ou moderada",
            "message": (
                f"O desconto empírico de {percent_br(applied)} está na faixa "
                "de até 10%."
            ),
            "band": "até 10%",
        }

    return {
        "level": "info",
        "title": "Sem desconto empírico positivo",
        "message": (
            "A razão entre Guias ITBI e ofertas não indicou superestimativa "
            "positiva das ofertas."
        ),
        "band": "0% empírico",
    }


def classify_sample_composition(
    n_itbi: int,
    n_offers: int,
    discount_source: str,
) -> dict[str, str]:
    """
    Classifica a suficiência operacional apenas para emissão de alertas.

    As faixas não bloqueiam o cálculo e não alteram o fator de oferta.
    """
    n_itbi = int(n_itbi)
    n_offers = int(n_offers)

    if discount_source == "offers_only_fallback":
        return {
            "level": "info",
            "title": "Amostra composta somente por ofertas",
            "message": (
                f"A amostra efetiva possui {n_offers} Oferta(s) e nenhuma Guia "
                "ITBI. Foi aplicado o fator convencional de 0,90, equivalente "
                "a desconto de 10%."
            ),
            "band": "somente ofertas — fator 0,90",
        }

    if n_offers == 0:
        return {
            "level": "success",
            "title": "Amostra sem ofertas",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guia(s) ITBI e nenhuma "
                "oferta. Não existe preço ofertado a ser ajustado."
            ),
            "band": "somente Guias ITBI",
        }

    minimum = min(n_itbi, n_offers)

    if n_itbi < 2 or n_offers < 2:
        return {
            "level": "error",
            "title": "Amostra mista insuficiente",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guia(s) ITBI e "
                f"{n_offers} Oferta(s). São necessários pelo menos dois dados "
                "de cada grupo para calcular a mediana por quantis pareados."
            ),
            "band": "amostra mista insuficiente",
        }

    if minimum < 10:
        return {
            "level": "warning",
            "title": "Amostra reduzida",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guias ITBI e "
                f"{n_offers} Ofertas. Um dos grupos tem menos de 10 dados, "
                "o que torna o desconto mais sensível à composição da amostra."
            ),
            "band": "menos de 10 em algum grupo",
        }

    if minimum < 15:
        return {
            "level": "info",
            "title": "Amostra restrita",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guias ITBI e "
                f"{n_offers} Ofertas. Há entre 10 e 14 dados no menor grupo; "
                "o resultado é utilizável, mas deve ser interpretado com cautela."
            ),
            "band": "10 a 14 no menor grupo",
        }

    imbalance = max(n_itbi, n_offers) / minimum
    if imbalance > 5:
        return {
            "level": "warning",
            "title": "Amostra numerosa, porém muito desequilibrada",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guias ITBI e "
                f"{n_offers} Ofertas. Ambos os grupos superam 15 dados, mas o "
                f"maior grupo é {imbalance:.1f} vezes o menor. Verifique se as "
                "distribuições permanecem comparáveis."
            ),
            "band": "15 ou mais, desequilíbrio superior a 5:1",
        }

    if imbalance > 3:
        return {
            "level": "info",
            "title": "Amostra suficiente, com desequilíbrio entre grupos",
            "message": (
                f"A amostra efetiva possui {n_itbi} Guias ITBI e "
                f"{n_offers} Ofertas. A quantidade mínima foi atendida, embora "
                f"o maior grupo seja {imbalance:.1f} vezes o menor."
            ),
            "band": "15 ou mais, desequilíbrio superior a 3:1",
        }

    return {
        "level": "success",
        "title": "Composição amostral adequada",
        "message": (
            f"A amostra efetiva possui {n_itbi} Guias ITBI e "
            f"{n_offers} Ofertas, com pelo menos 15 dados em cada grupo."
        ),
        "band": "15 ou mais em ambos os grupos",
    }


def render_quality_alert(alert: dict[str, str]) -> None:
    title = alert["title"]
    message = alert["message"]
    content = f"**{title}.** {message}"

    if alert["level"] == "error":
        st.error(content)
    elif alert["level"] == "warning":
        st.warning(content)
    elif alert["level"] == "success":
        st.success(content)
    else:
        st.info(content)


def risk_card(level: str, confidence: int, reasons: list[str]) -> None:
    css_level = {
        "baixo": "low",
        "moderado": "moderate",
        "alto": "high",
    }.get(level, "moderate")
    reason = reasons[0] if reasons else "Boa aderência aos dados observados."
    st.markdown(
        f"""
        <div class="risk-card {css_level}">
            <div class="risk-label">Confiabilidade</div>
            <div class="risk-value">{confidence}/100 · risco {level}</div>
            <div class="risk-text">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def unique_preserve_order(values: list[str | None]) -> list[str]:
    """Remove repetições preservando a primeira ocorrência e a ordem."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def make_unique_column_names(columns) -> list[str]:
    """Garante nomes únicos mesmo após renomeações ou cabeçalhos repetidos."""
    counts: dict[str, int] = {}
    result: list[str] = []

    for raw_name in columns:
        name = str(raw_name)
        occurrence = counts.get(name, 0)
        counts[name] = occurrence + 1
        result.append(name if occurrence == 0 else f"{name}_{occurrence + 1}")

    return result



def first_named_series(df: pd.DataFrame, column_name: str) -> pd.Series:
    """
    Retorna a primeira coluna com o nome solicitado.

    A proteção é necessária para planilhas que eventualmente contenham
    cabeçalhos repetidos.
    """
    matches = np.flatnonzero(np.asarray(df.columns, dtype=str) == str(column_name))
    if matches.size == 0:
        return pd.Series(index=df.index, dtype=float)
    return df.iloc[:, int(matches[0])]


def coordinate_to_numeric(series: pd.Series) -> pd.Series:
    """
    Converte coordenadas numéricas e textos com vírgula decimal.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def calculate_map_zoom(points: pd.DataFrame) -> float:
    """
    Estima um zoom legível a partir da dispersão espacial dos pontos.
    """
    if points.empty or len(points) == 1:
        return 15.0

    lat_span = float(points["latitude"].max() - points["latitude"].min())
    lon_span = float(points["longitude"].max() - points["longitude"].min())
    span = max(lat_span, lon_span)

    if span <= 0.002:
        return 15.5
    if span <= 0.005:
        return 14.5
    if span <= 0.010:
        return 13.8
    if span <= 0.030:
        return 12.5
    if span <= 0.080:
        return 11.3
    if span <= 0.200:
        return 10.2
    if span <= 0.500:
        return 9.0
    return 7.8


def build_map_data(
    neighbors: pd.DataFrame,
    latitude_column: str,
    longitude_column: str,
    target_latitude: float,
    target_longitude: float,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    Prepara pontos válidos para o mapa e informa quantos comparáveis foram
    descartados por coordenadas ausentes ou fora dos limites geográficos.
    """
    latitude = coordinate_to_numeric(
        first_named_series(neighbors, latitude_column)
    )
    longitude = coordinate_to_numeric(
        first_named_series(neighbors, longitude_column)
    )

    comparable_points = pd.DataFrame(
        {
            "latitude": latitude,
            "longitude": longitude,
        },
        index=neighbors.index,
    )

    if "_peso_knn" in neighbors.columns:
        comparable_points["peso"] = pd.to_numeric(
            first_named_series(neighbors, "_peso_knn"),
            errors="coerce",
        )
    else:
        comparable_points["peso"] = np.nan

    if "_distancia_geografica_km" in neighbors.columns:
        comparable_points["distancia_km"] = pd.to_numeric(
            first_named_series(neighbors, "_distancia_geografica_km"),
            errors="coerce",
        )
    else:
        comparable_points["distancia_km"] = np.nan

    comparable_points["tipo_ponto"] = "Comparável"
    comparable_points["ordem"] = np.arange(1, len(comparable_points) + 1)
    comparable_points["peso_texto"] = comparable_points["peso"].map(
        lambda value: (
            f"{value * 100:.2f}%"
            if pd.notna(value) and np.isfinite(value)
            else "—"
        )
    )
    comparable_points["distancia_texto"] = comparable_points[
        "distancia_km"
    ].map(
        lambda value: (
            f"{value:.3f} km"
            if pd.notna(value) and np.isfinite(value)
            else "—"
        )
    )

    valid_comparable = (
        comparable_points["latitude"].between(-90, 90)
        & comparable_points["longitude"].between(-180, 180)
        & comparable_points["latitude"].notna()
        & comparable_points["longitude"].notna()
    )
    discarded = int((~valid_comparable).sum())
    comparable_points = comparable_points.loc[valid_comparable].copy()

    target_points = pd.DataFrame(
        [
            {
                "latitude": pd.to_numeric(
                    pd.Series([target_latitude]), errors="coerce"
                ).iloc[0],
                "longitude": pd.to_numeric(
                    pd.Series([target_longitude]), errors="coerce"
                ).iloc[0],
                "tipo_ponto": "Imóvel avaliando",
                "ordem": 0,
                "peso": np.nan,
                "peso_texto": "—",
                "distancia_km": 0.0,
                "distancia_texto": "0,000 km",
            }
        ]
    )

    valid_target = (
        target_points["latitude"].between(-90, 90)
        & target_points["longitude"].between(-180, 180)
        & target_points["latitude"].notna()
        & target_points["longitude"].notna()
    )
    target_points = target_points.loc[valid_target].copy()

    return comparable_points, target_points, discarded


def render_comparables_map(
    neighbors: pd.DataFrame,
    latitude_column: str,
    longitude_column: str,
    target_latitude: float,
    target_longitude: float,
) -> None:
    """
    Exibe um mapa de proximidade autossuficiente.

    O gráfico não depende de WebGL, Mapbox, tiles externos ou componentes
    JavaScript. As coordenadas são convertidas em deslocamentos aproximados
    em quilômetros em relação ao imóvel avaliando.
    """
    comparable_points, target_points, discarded = build_map_data(
        neighbors=neighbors,
        latitude_column=latitude_column,
        longitude_column=longitude_column,
        target_latitude=target_latitude,
        target_longitude=target_longitude,
    )

    if target_points.empty:
        st.warning(
            "O mapa não pôde ser exibido porque as coordenadas do imóvel "
            "avaliando são inválidas."
        )
        return

    target_lat = float(target_points.iloc[0]["latitude"])
    target_lon = float(target_points.iloc[0]["longitude"])

    if discarded:
        st.warning(
            f"{discarded} comparável(is) não foi(ram) incluído(s) no mapa "
            "porque possuíam latitude ou longitude inválida."
        )

    if comparable_points.empty:
        st.warning(
            "Não existem comparáveis com coordenadas válidas para representar."
        )
        return

    latitude_scale_km = 111.32
    longitude_scale_km = 111.32 * np.cos(np.radians(target_lat))
    longitude_scale_km = max(abs(longitude_scale_km), 1e-6)

    comparable_points = comparable_points.copy()
    comparable_points["deslocamento_leste_km"] = (
        comparable_points["longitude"] - target_lon
    ) * longitude_scale_km
    comparable_points["deslocamento_norte_km"] = (
        comparable_points["latitude"] - target_lat
    ) * latitude_scale_km

    weights = pd.to_numeric(
        comparable_points["peso"],
        errors="coerce",
    ).fillna(0.0)

    if weights.max() > 0:
        marker_sizes = 80 + 520 * (weights / weights.max())
    else:
        marker_sizes = pd.Series(
            np.full(len(comparable_points), 180.0),
            index=comparable_points.index,
        )

    fig, ax = plt.subplots(figsize=(11.5, 6.2))

    ax.scatter(
        comparable_points["deslocamento_leste_km"],
        comparable_points["deslocamento_norte_km"],
        s=marker_sizes,
        alpha=0.78,
        edgecolors="white",
        linewidths=1.2,
        label="Comparáveis",
        zorder=3,
    )

    ax.scatter(
        [0.0],
        [0.0],
        s=340,
        marker="*",
        edgecolors="white",
        linewidths=1.4,
        label="Imóvel avaliando",
        zorder=5,
    )

    comparable_points = comparable_points.sort_values(
        "peso",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    for position, row in comparable_points.iterrows():
        label = str(position + 1)
        ax.annotate(
            label,
            (
                row["deslocamento_leste_km"],
                row["deslocamento_norte_km"],
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8.5,
            fontweight="bold",
            zorder=6,
        )

    all_x = np.concatenate(
        [
            comparable_points["deslocamento_leste_km"].to_numpy(dtype=float),
            np.array([0.0]),
        ]
    )
    all_y = np.concatenate(
        [
            comparable_points["deslocamento_norte_km"].to_numpy(dtype=float),
            np.array([0.0]),
        ]
    )

    max_extent = max(
        float(np.nanmax(np.abs(all_x))) if all_x.size else 0.0,
        float(np.nanmax(np.abs(all_y))) if all_y.size else 0.0,
        0.25,
    )
    padding = max_extent * 0.18 + 0.08

    ax.set_xlim(float(np.nanmin(all_x)) - padding, float(np.nanmax(all_x)) + padding)
    ax.set_ylim(float(np.nanmin(all_y)) - padding, float(np.nanmax(all_y)) + padding)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axhline(0, linewidth=0.7, alpha=0.35, zorder=1)
    ax.axvline(0, linewidth=0.7, alpha=0.35, zorder=1)
    ax.grid(True, linewidth=0.6, alpha=0.25)
    ax.set_xlabel("Deslocamento leste–oeste em relação ao avaliando (km)")
    ax.set_ylabel("Deslocamento norte–sul em relação ao avaliando (km)")
    ax.set_title("Mapa de proximidade dos comparáveis", loc="left", pad=14)
    ax.legend(loc="best", frameon=True)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.caption(
        "O tamanho dos círculos representa o peso do comparável no KNN. "
        "Os números correspondem à ordem decrescente de peso. As distâncias "
        "são aproximações planas calculadas a partir de latitude e longitude."
    )

    map_table = comparable_points[
        [
            "ordem",
            "peso",
            "distancia_km",
            "latitude",
            "longitude",
            "deslocamento_leste_km",
            "deslocamento_norte_km",
        ]
    ].copy()
    map_table.insert(
        0,
        "posição_no_mapa",
        np.arange(1, len(map_table) + 1),
    )

    with st.expander("Identificação dos pontos do mapa"):
        map_display = map_table.copy()
        map_display["peso_percentual"] = (
            pd.to_numeric(map_display["peso"], errors="coerce") * 100
        )
        map_display = map_display.drop(columns=["peso"])

        st.dataframe(
            map_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "peso_percentual": st.column_config.NumberColumn(
                    "Peso",
                    format="%.2f%%",
                ),
                "distancia_km": st.column_config.NumberColumn(
                    "Distância",
                    format="%.3f km",
                ),
                "deslocamento_leste_km": st.column_config.NumberColumn(
                    "Leste–oeste",
                    format="%.3f km",
                ),
                "deslocamento_norte_km": st.column_config.NumberColumn(
                    "Norte–sul",
                    format="%.3f km",
                ),
                "latitude": st.column_config.NumberColumn(format="%.7f"),
                "longitude": st.column_config.NumberColumn(format="%.7f"),
            },
        )

def dataframe_to_excel(
    neighbors: pd.DataFrame,
    diagnostics: dict,
) -> bytes:
    output = BytesIO()
    diagnostics_df = pd.DataFrame(
        [
            {"indicador": key, "valor": str(value)}
            for key, value in diagnostics.items()
            if key not in {"feature_coverage", "risk_reasons"}
        ]
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        neighbors.to_excel(writer, sheet_name="Comparaveis", index=False)
        diagnostics_df.to_excel(writer, sheet_name="Diagnosticos", index=False)

        worksheet = writer.sheets["Comparaveis"]
        headers = {cell.value: cell.column for cell in worksheet[1]}

        for column_name in ("peso_knn",):
            column_number = headers.get(column_name)
            if column_number is None:
                continue
            for row_number in range(2, worksheet.max_row + 1):
                worksheet.cell(
                    row=row_number,
                    column=column_number,
                ).number_format = "0.00%"

        for column_name in (
            "valor_unitario_original",
            "valor_unitario_ajustado",
            "valor_unitario_robusto",
            "contribuicao_valor_unitario",
        ):
            column_number = headers.get(column_name)
            if column_number is None:
                continue
            for row_number in range(2, worksheet.max_row + 1):
                worksheet.cell(
                    row=row_number,
                    column=column_number,
                ).number_format = 'R$ #,##0.00'

    output.seek(0)
    return output.getvalue()


st.markdown(
    f"""
    <div class="hero">
        <span class="badge">{APP_NAME} · {APP_EDITION}</span>
        <h1>Estimativa imobiliária por comparáveis, em poucos passos.</h1>
        <p>
            Envie uma planilha SIRI, informe as características do imóvel e
            obtenha uma estimativa com tratamento automático de ofertas,
            duplicidades, valores extremos e extrapolação.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

step_header(1, "Carregue a planilha")

with st.container(border=True):
    uploaded = st.file_uploader(
        "Arquivo Excel",
        type=["xlsx", "xlsm", "xls"],
        help="O arquivo é processado em memória durante esta sessão.",
    )

if uploaded is None:
    st.markdown(
        """
        <div class="helper">
            Use uma planilha exportada do SIRI contendo tipo da informação,
            finalidade, valor, coordenadas e características de área.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

file_bytes = uploaded.getvalue()
file_hash = hashlib.sha1(file_bytes).hexdigest()

try:
    excel_file = pd.ExcelFile(BytesIO(file_bytes))
except Exception as exc:
    st.error(f"Não foi possível abrir o Excel: {exc}")
    st.stop()

if len(excel_file.sheet_names) == 1:
    sheet = excel_file.sheet_names[0]
else:
    sheet = st.selectbox("Planilha a utilizar", excel_file.sheet_names)

file_signature = f"{file_hash}:{sheet}"
if st.session_state.get("_lite_file_signature") != file_signature:
    st.session_state["_lite_file_signature"] = file_signature
    st.session_state.pop("lite_result", None)
    st.session_state.pop("_lite_last_context", None)

try:
    original_df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet)
except Exception as exc:
    st.error(f"Não foi possível ler a planilha: {exc}")
    st.stop()

if original_df.empty:
    st.error("A planilha selecionada está vazia.")
    st.stop()

original_df.columns = [str(column) for column in original_df.columns]
df, schema_info = enrich_known_schemas(original_df)
mapping, missing_fields = build_mapping(df)

if mapping is None:
    st.error(
        "A planilha não possui todos os campos necessários para a edição LITE."
    )
    st.write("Campos não identificados: " + ", ".join(missing_fields) + ".")
    st.caption(
        "Esta edição foi preparada para a estrutura SIRI e não possui "
        "mapeamento manual de colunas."
    )
    st.stop()

if schema_info.siri_detected:
    st.success(
        f"Planilha reconhecida: {len(df):,} registros.".replace(",", ".")
    )
else:
    st.info(
        "A estrutura principal foi reconhecida automaticamente, embora o "
        "arquivo não contenha todos os marcadores do padrão SIRI completo."
    )

purpose_series = (
    df[mapping.finalidade_oferta]
    .dropna()
    .astype(str)
    .str.strip()
)
purposes = sorted(value for value in purpose_series.unique() if value)
if not purposes:
    st.error("Não foram encontradas finalidades imobiliárias válidas.")
    st.stop()

step_header(2, "Informe o imóvel")

selected_purpose = st.selectbox("Finalidade do imóvel", purposes)

suggested_mode = (
    "Terreno ou lote"
    if purpose_suggests_territorial(selected_purpose)
    else "Unidade construída"
)

context_key = f"{file_signature}:{selected_purpose}"
if st.session_state.get("_lite_last_context") != context_key:
    st.session_state["_lite_last_context"] = context_key
    st.session_state["lite_property_mode"] = suggested_mode
    st.session_state.pop("lite_result", None)

property_mode = st.radio(
    "Tipo de imóvel",
    ["Terreno ou lote", "Unidade construída"],
    horizontal=True,
    key="lite_property_mode",
)
territorial = property_mode == "Terreno ou lote"

purpose_mask = df[mapping.finalidade_oferta].map(normalize_text).eq(
    normalize_text(selected_purpose)
)
purpose_types = df.loc[purpose_mask, mapping.tipo_informacao].map(normalize_text)

s1, s2, s3 = st.columns(3)
s1.metric("Dados disponíveis", int(purpose_mask.sum()))
s2.metric("Guias ITBI", int(purpose_types.eq("guia itbi").sum()))
s3.metric("Ofertas", int(purpose_types.eq("oferta").sum()))

if territorial:
    if not mapping.siat_area_total_lote:
        st.error("A planilha não possui uma área de terreno utilizável.")
        st.stop()
    if not mapping.testada:
        st.error("A planilha não possui uma coluna de TESTADA utilizável.")
        st.stop()
else:
    if not mapping.area_privativa and not mapping.area_construida:
        st.error(
            "A planilha não possui área privativa nem área construída utilizável."
        )
        st.stop()

with st.form("lite_property_form"):
    with st.container(border=True):
        if territorial:
            c1, c2 = st.columns(2)
            with c1:
                target_area_lote = st.number_input(
                    "Área total do lote (m²)",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                )
            with c2:
                target_testada = st.number_input(
                    "Testada (m)",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    help="Comprimento da frente principal do terreno.",
                )
            target_area_privativa = 0.0
            target_area_construida = 0.0
        else:
            c1, c2 = st.columns(2)
            with c1:
                target_area_privativa = (
                    st.number_input(
                        "Área privativa (m²)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        help=(
                            "Para apartamentos, salas e lojas, esta costuma "
                            "ser a principal área de referência."
                        ),
                    )
                    if mapping.area_privativa
                    else 0.0
                )
            with c2:
                target_area_construida = (
                    st.number_input(
                        "Área construída (m²)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                    )
                    if mapping.area_construida
                    else 0.0
                )
            target_area_lote = 0.0
            target_testada = 0.0

        c3, c4 = st.columns(2)
        with c3:
            target_latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=-30.0300000,
                format="%.7f",
            )
        with c4:
            target_longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=-51.2300000,
                format="%.7f",
            )

        calculate = st.form_submit_button(
            "Calcular estimativa",
            type="primary",
            use_container_width=True,
        )

if calculate:
    try:
        if territorial:
            if target_area_lote <= 0:
                raise ValueError("Informe a área total do lote.")
            if target_testada <= 0:
                raise ValueError("Informe a testada do terreno.")
            reference_area_column = mapping.siat_area_total_lote
        else:
            if target_area_privativa > 0 and mapping.area_privativa:
                reference_area_column = mapping.area_privativa
            elif target_area_construida > 0 and mapping.area_construida:
                reference_area_column = mapping.area_construida
            else:
                raise ValueError(
                    "Informe a área privativa ou a área construída."
                )

        target = {
            "area_construida": (
                target_area_construida
                if target_area_construida > 0
                else None
            ),
            "area_privativa": (
                target_area_privativa
                if target_area_privativa > 0
                else None
            ),
            "siat_area_total_lote": (
                target_area_lote if target_area_lote > 0 else None
            ),
            "testada": target_testada if target_testada > 0 else None,
            "latitude": target_latitude,
            "longitude": target_longitude,
        }

        reference_key = {
            mapping.area_construida: "area_construida",
            mapping.area_privativa: "area_privativa",
            mapping.siat_area_total_lote: "siat_area_total_lote",
        }.get(reference_area_column)
        if reference_key:
            target[reference_area_column] = target[reference_key]

        original_columns = [str(column) for column in original_df.columns]
        duplicate_date_column = choose_existing(
            original_columns,
            [
                "data_encaminhamento",
                "data_registro",
                "data_coleta",
                "data_anuncio",
                "data",
            ],
        )
        duplicate_identifier_columns = tuple(
            column
            for column in (
                "anuncio_website",
                "imobiliaria_codigo_anuncio",
                "origem_registro",
                "idf_registro",
                "id_anuncio",
                "codigo_anuncio",
            )
            if column in original_columns
        )

        preparation = prepare_data(
            df=df,
            mapping=mapping,
            selected_purpose=selected_purpose,
            value_kind=detect_value_kind(mapping.valor),
            reference_area_column=reference_area_column,
            discount_cap=DISCOUNT_CAP,
            remove_offer_duplicates=True,
            duplicate_date_column=duplicate_date_column,
            duplicate_identifier_columns=duplicate_identifier_columns,
        )

        estimate = estimate_knn(
            preparation=preparation,
            mapping=mapping,
            target=target,
            reference_area_column=reference_area_column,
            min_k=MIN_K,
            max_k=MAX_K,
            min_effective_neighbors=MIN_EFFECTIVE_NEIGHBORS,
            similarity_weight=SIMILARITY_WEIGHT,
            distance_power=DISTANCE_POWER,
            max_individual_weight=MAX_INDIVIDUAL_WEIGHT,
            robust_mad_threshold=ROBUST_MAD_THRESHOLD,
            territorial=territorial,
        )

        st.session_state["lite_result"] = {
            "preparation": preparation,
            "estimate": estimate,
            "mapping": mapping,
            "purpose": selected_purpose,
            "territorial": territorial,
            "reference_area_column": reference_area_column,
            "target": target,
            "duplicate_date_column": duplicate_date_column,
        }
    except Exception as exc:
        st.error(str(exc))

run = st.session_state.get("lite_result")
if run is None:
    st.markdown(
        """
        <div class="helper">
            O aplicativo escolherá automaticamente os comparáveis e reduzirá
            a influência de anúncios repetidos, imóveis isolados e valores
            unitários extremos.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

preparation: PreparationResult = run["preparation"]
estimate: EstimateResult = run["estimate"]
mapping = run["mapping"]

step_header(3, "Veja o resultado")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Valor total estimado", money_br(estimate.estimated_total_value))
m2.metric(
    "Valor unitário estimado",
    f"{money_br(estimate.estimated_unit_value)}/m²",
)
m3.metric(
    "Comparáveis utilizados",
    str(estimate.diagnostics["k_used"]),
    delta=f"{estimate.effective_neighbors:.1f} efetivos",
    delta_color="off",
)
m4.metric(
    "Desconto das ofertas",
    percent_br(preparation.discount),
    delta="limitado a 20%",
    delta_color="off",
)

raw_discount = preparation.diagnostics.get(
    "raw_discount_median",
    np.nan,
)
discount_source = preparation.diagnostics.get(
    "discount_source",
    "empirical_ratio",
)
n_itbi_effective = int(preparation.diagnostics.get("n_itbi", 0))
n_offer_effective = int(preparation.diagnostics.get("n_offer", 0))

discount_alert = classify_discount_alert(
    preparation.discount,
    raw_discount,
    discount_source,
)
sample_alert = classify_sample_composition(
    n_itbi_effective,
    n_offer_effective,
    discount_source,
)

with st.container(border=True):
    st.markdown("#### Qualidade do fator de oferta")
    qa1, qa2 = st.columns(2)
    with qa1:
        render_quality_alert(discount_alert)
    with qa2:
        render_quality_alert(sample_alert)
    st.caption(
        "Regra aplicada: somente ofertas recebem desconto convencional de 10%. "
        "Quando existem Guias ITBI e ofertas suficientes, utiliza-se a mediana "
        "dos quantis pareados, com 20% apenas como freio do resultado empírico."
    )

tabs = st.tabs(["Resumo", "Comparáveis e mapa"])

with tabs[0]:
    left, right = st.columns([1.45, 1])

    with left:
        with st.container(border=True):
            st.markdown("#### Interpretação")
            dispersion = (
                estimate.weighted_std_unit / estimate.estimated_unit_value
                if estimate.estimated_unit_value > 0
                else np.nan
            )
            st.write(
                f"A estimativa foi formada por **{estimate.diagnostics['k_used']} "
                f"comparáveis**, equivalentes a **{estimate.effective_neighbors:.2f} "
                "vizinhos efetivos** após o controle de concentração."
            )
            st.write(
                f"A dispersão entre os comparáveis ficou em "
                f"**{percent_br(dispersion)}** do valor unitário estimado."
            )
            st.write(
                f"O maior peso individual foi de "
                f"**{percent_br(estimate.diagnostics['max_weight_observed'])}**."
            )
            st.progress(estimate.diagnostics["confidence_score"] / 100)
            st.caption(
                "A pontuação considera semelhança física, localização, "
                "concentração dos pesos e necessidade de tratamento robusto."
            )

    with right:
        risk_card(
            estimate.diagnostics["risk_level"],
            estimate.diagnostics["confidence_score"],
            estimate.diagnostics["risk_reasons"],
        )

    risk_reasons = estimate.diagnostics["risk_reasons"]
    if risk_reasons:
        with st.expander("Pontos de atenção"):
            for reason in risk_reasons:
                st.warning(reason)

    duplicates_removed = int(
        preparation.diagnostics.get("offer_duplicates_removed", 0)
    )
    st.info(
        f"Foram removidos **{duplicates_removed}** registros repetidos de "
        "ofertas antes da estimativa."
    )

    discount_warning = preparation.diagnostics.get("discount_warning")
    if (
        discount_warning
        and discount_source not in {"offers_only_fallback", "empirical_ratio"}
    ):
        st.warning(discount_warning)

with tabs[1]:
    neighbors = estimate.neighbors.copy()

    relevant_columns = unique_preserve_order(
        [
            "_row_excel",
            mapping.tipo_informacao,
            mapping.finalidade_oferta,
            mapping.valor,
            run["reference_area_column"],
            mapping.area_construida,
            mapping.area_privativa,
            mapping.siat_area_total_lote,
            mapping.testada,
            mapping.latitude,
            mapping.longitude,
            "_valor_unitario_original",
            "_valor_unitario_ajustado",
            "_valor_unitario_robusto",
            "_distancia_geografica_km",
            "_peso_knn",
            "_contribuicao_valor_unitario",
        ]
    )
    relevant_columns = [
        column for column in relevant_columns if column in neighbors.columns
    ]

    rename = {
        "_row_excel": "linha_excel",
        "_valor_unitario_original": "valor_unitario_original",
        "_valor_unitario_ajustado": "valor_unitario_ajustado",
        "_valor_unitario_robusto": "valor_unitario_robusto",
        "_distancia_geografica_km": "distancia_geografica_km",
        "_peso_knn": "peso_knn",
        "_contribuicao_valor_unitario": "contribuicao_valor_unitario",
    }

    neighbors_export = (
        neighbors.loc[:, relevant_columns]
        .rename(columns=rename)
        .sort_values("peso_knn", ascending=False)
    )

    # Proteção adicional contra cabeçalhos repetidos no arquivo de origem
    # ou colisões produzidas após a renomeação.
    neighbors_export.columns = make_unique_column_names(
        neighbors_export.columns
    )

    neighbors_display = neighbors_export.copy()
    weight_column = next(
        (
            column
            for column in neighbors_display.columns
            if column == "peso_knn" or column.startswith("peso_knn_")
        ),
        None,
    )
    if weight_column is not None:
        neighbors_display["peso_percentual"] = (
            pd.to_numeric(
                neighbors_display[weight_column],
                errors="coerce",
            )
            * 100
        )
        neighbors_display = neighbors_display.drop(columns=[weight_column])

    st.dataframe(
        neighbors_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "peso_percentual": st.column_config.NumberColumn(
                "Peso",
                format="%.2f%%",
            ),
            "distancia_geografica_km": st.column_config.NumberColumn(
                "Distância",
                format="%.3f km",
            ),
            "valor_unitario_original": st.column_config.NumberColumn(
                format="R$ %.2f",
            ),
            "valor_unitario_ajustado": st.column_config.NumberColumn(
                format="R$ %.2f",
            ),
            "valor_unitario_robusto": st.column_config.NumberColumn(
                format="R$ %.2f",
            ),
            "contribuicao_valor_unitario": st.column_config.NumberColumn(
                format="R$ %.2f",
            ),
        },
    )

    st.markdown("#### Localização dos comparáveis")
    render_comparables_map(
        neighbors=neighbors,
        latitude_column=mapping.latitude,
        longitude_column=mapping.longitude,
        target_latitude=run["target"]["latitude"],
        target_longitude=run["target"]["longitude"],
    )

diagnostics = {
    "aplicativo": APP_NAME,
    "edicao": APP_EDITION,
    "finalidade": run["purpose"],
    "valor_total_estimado": estimate.estimated_total_value,
    "valor_unitario_estimado": estimate.estimated_unit_value,
    "area_referencia": run["reference_area_column"],
    "faixa_alerta_desconto": discount_alert["band"],
    "classificacao_desconto": discount_alert["title"],
    "faixa_composicao_amostral": sample_alert["band"],
    "classificacao_composicao_amostral": sample_alert["title"],
    "guias_itbi_efetivas": n_itbi_effective,
    "ofertas_efetivas": n_offer_effective,
    **preparation.diagnostics,
    **estimate.diagnostics,
}

excel_bytes = dataframe_to_excel(neighbors_export, diagnostics)
st.download_button(
    "Baixar resultado em Excel",
    data=excel_bytes,
    file_name="resultado_estimador_knn_siri.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

with st.expander("Como o estimador trabalha"):
    st.markdown(
        """
- considera apenas a finalidade escolhida;
- exclui ofertas de aluguel;
- mantém somente a coleta mais recente de cada oferta repetida;
- aplica fator 0,90 quando a amostra contém somente ofertas;
- havendo transações e ofertas suficientes, calcula a mediana da razão observada;
- usa 20% apenas como freio do desconto empírico;
- alerta quando o desconto é moderado, relevante, elevado ou supera o freio;
- informa se a quantidade de Guias ITBI e Ofertas é insuficiente, restrita ou adequada;
- escolhe automaticamente o número de comparáveis;
- impede que um único imóvel concentre peso excessivo;
- reduz a influência de valores unitários extremos;
- verifica se o imóvel está fora da faixa observada na base;
- apresenta o valor, a confiança, os comparáveis e o mapa.
        """
    )
