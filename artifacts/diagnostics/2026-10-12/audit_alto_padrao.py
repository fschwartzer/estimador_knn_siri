"""Auditoria descritiva do alto valor unitário, sem alterar a VERA ou o SIRI.

Execução: python artifacts/diagnostics/2026-10-12/audit_alto_padrao.py
Preços altos são um marcador exploratório, não uma classificação de padrão.
Os filtros de preparação são os mesmos do aplicativo no regime preferido.
"""
from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT_CORE = Path(__file__).with_name("core_before.py")
_spec = importlib.util.spec_from_file_location("vera_core_before_high_value_fix", OUT_CORE)
core = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = core
_spec.loader.exec_module(core)
import estimador_knn_schema_v6120 as schema
from calibration_audit import SOURCE, file_sha256
from calibrate_siri import metrics

OUT = Path(__file__).resolve().parent
CAL = ROOT / "artifacts/calibration/2026-09-23"
PURPOSES = ("APARTAMENTO", "COBERTURA", "CASA / RESIDENCIA")
RECENT = pd.Timestamp("2026-04-01")
THRESHOLDS = (10000, 15000, 20000, 30000)


def log(message):
    print(message, flush=True)


def save_json(name, value):
    # JSON estrito: valores não finitos são ausências, não tokens NaN/Infinity.
    def clean(item):
        if isinstance(item, dict):
            return {str(k): clean(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v) for v in item]
        if isinstance(item, (np.integer,)):
            return int(item)
        if isinstance(item, (float, np.floating)):
            return float(item) if np.isfinite(item) else None
        return item
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    provenance = json.loads((CAL / "provenance.json").read_text(encoding="utf-8"))
    source_hash = file_sha256(SOURCE)
    if source_hash != provenance["source_sha256"]:
        raise ValueError("A planilha não corresponde à proveniência do cache.")
    log("Proveniência da planilha conferida. Lendo cache residencial da calibração.")
    cached = pd.read_pickle(CAL / "enriched.pkl")
    raw_rows = len(cached)
    keep = ["_row_excel", "data_encaminhamento", "siat_inscricao", "siat_bairro",
            "siat_finalidade_descricao", "crawler_tipo_imovel_normalizado", "tipo_informacao",
            "siat_area_terreno", "siat_testada_terreno", "siat_area_construida",
            "crawler_area_terreno", "crawler_area_construida", "crawler_area_privativa",
            "valor_oferta", "siat_latitude", "siat_longitude", "siat_ano",
            "anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"]
    residential = cached[schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA].map(core.normalize_text).isin([core.normalize_text(p) for p in PURPOSES])
    derived = [schema.DERIVED_TIPO_INFORMACAO, schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA,
        schema.DERIVED_AREA_CONSTRUIDA, schema.DERIVED_AREA_PRIVATIVA, schema.DERIVED_AREA_LOTE,
        schema.DERIVED_TESTADA, schema.DERIVED_CONFLITO_TIPOLOGICO]
    data = cached.loc[residential, keep + derived].copy()
    del cached
    # O diff entre schema_original.py e o atual altera só terrenos em condomínio.
    # Confere ainda uma amostra residencial contra a normalização atual.
    sample = data.sample(min(300, len(data)), random_state=12102026)
    current, _ = schema.enrich_known_schemas(sample[keep])
    for col in derived:
        pd.testing.assert_series_equal(current[col], sample[col], check_dtype=False, check_names=False)
    log("Derivações residenciais do cache reconciliadas com o schema atual.")
    data["_date"] = core._parse_registration_dates(data["data_encaminhamento"])
    mapping = core.ColumnMapping(schema.DERIVED_TIPO_INFORMACAO, schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA,
        "valor_oferta", schema.DERIVED_AREA_CONSTRUIDA, schema.DERIVED_AREA_PRIVATIVA,
        "siat_latitude", "siat_longitude", schema.DERIVED_AREA_LOTE, schema.DERIVED_TESTADA, "siat_ano")
    numbers = [mapping.valor, mapping.area_construida, mapping.area_privativa,
               mapping.siat_area_total_lote, mapping.testada, mapping.latitude, mapping.longitude, mapping.ano_construcao]
    for col in numbers:
        data[col] = core.to_numeric(data[col])
    data["_type"] = data[mapping.tipo_informacao].map(core.normalize_text)
    data["_purpose"] = data[mapping.finalidade_oferta]
    summary = {"source": str(SOURCE), "source_sha256": source_hash, "raw_rows": raw_rows,
        "date_min": str(data["_date"].min()), "date_max": str(data["_date"].max()),
        "recent_since": str(RECENT.date()), "schema_sha256": file_sha256(ROOT / "estimador_knn_schema_v6120.py"),
        "core_sha256": file_sha256(OUT_CORE),
        "cached_schema_sha256": file_sha256(CAL / "schema_original.py"),
        "cached_residential_validation_sample": 300, "purposes": []}
    threshold_rows, exclusion_rows, test_rows, simulation_rows, simulation_neighbors = [], [], [], [], []
    for purpose in PURPOSES:
        log(f"Auditando preparação e cauda superior: {purpose}")
        group = data.loc[data["_purpose"].map(core.normalize_text).eq(core.normalize_text(purpose))].copy()
        if group.empty:
            raise ValueError(f"Finalidade sem registros: {purpose}")
        ref = mapping.area_construida if schema.reference_area_preference(purpose) == "construida" else mapping.area_privativa
        params = core.calibrated_parameters_for_purpose(purpose)
        group["_raw_vu"] = group[mapping.valor] / group[ref]
        preparation = core.prepare_data(group, mapping, purpose, "Valor total", ref,
            duplicate_date_column="data_encaminhamento", duplicate_registration_column="siat_inscricao",
            duplicate_value_column="valor_oferta",
            duplicate_identifier_columns=("anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"),
            conflict_column=schema.DERIVED_CONFLITO_TIPOLOGICO, minimum_without_conflict=int(params["min_k"]))
        eligible_source = group.loc[group["_type"].isin([core.TIPO_ITBI, core.TIPO_OFERTA])].copy()
        eligible_source["_tipo_norm"] = eligible_source["_type"]
        # Etapas anteriores ao pré-filtro, reproduzidas só para reconciliar contagens.
        if preparation.diagnostics.get("conflict_policy") == "exclusão prioritária":
            log("Política de conflitos requer conferência da classificação das etapas.")
        clean_source = eligible_source.loc[~eligible_source[schema.DERIVED_CONFLITO_TIPOLOGICO].map(core.normalize_text).isin(core.CONFLICT_TYPOLOGICAL_VALUES)].copy()
        if preparation.diagnostics.get("conflict_fallback_used", False):
            clean_source = eligible_source
        dedup, _ = core.deduplicate_offers(clean_source, "data_encaminhamento",
            ("anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"), "siat_inscricao", "valor_oferta")
        prefilter_kept, prefilter_excluded, _, prefilter_diag = core._safe_market_prefilter(dedup, mapping, ref, "Valor total", purpose)
        if set(prefilter_kept["_row_excel"]) != set(preparation.data["_row_excel"]):
            raise AssertionError("Etapas de diagnóstico não reconciliam com a preparação real.")
        stat = prefilter_excluded.loc[prefilter_excluded["_etapa_controle"].eq("filtro robusto automático")].copy()
        upper = stat.loc[stat["_valor_unitario_original"].gt(prefilter_diag["prefilter_upper_vu"])].copy()
        phys, _ = core._valid_candidates(preparation.data, mapping, [("area_construida" if ref == mapping.area_construida else "area_privativa", ref)], True)
        with_year = phys.loc[core.valid_construction_year_mask(phys[mapping.ano_construcao])]
        stages = {"bruto": eligible_source, "sem_conflito": clean_source, "deduplicado": dedup,
            "apos_prefiltro": preparation.data, "com_coordenadas": phys, "com_coordenadas_e_ano": with_year}
        if purpose == "APARTAMENTO":
            neighborhood_rows = []
            for stage, frame in stages.items():
                neighborhood = frame.loc[frame["siat_bairro"].map(core.normalize_text).isin(["moinhos de vento", "moinhos vento"])].copy()
                for (typ, yr), selected in neighborhood.groupby(["_type", "siat_ano"], dropna=False):
                    vu = selected[mapping.valor] / selected[ref]
                    neighborhood_rows.append({"stage":stage, "type":typ, "construction_year":yr, "n":len(selected),
                        "unique_registrations":selected["siat_inscricao"].nunique(),
                        "recent_n":int(selected["_date"].ge(RECENT).sum()),
                        "vu_median":vu.median(), "vu_max":vu.max(),
                        "date_max":str(selected["_date"].max())})
            pd.DataFrame(neighborhood_rows).to_csv(OUT / "moinhos_anos_por_etapa.csv", index=False, encoding="utf-8-sig")
            moinhos = group.loc[group["siat_bairro"].map(core.normalize_text).isin(["moinhos de vento", "moinhos vento"])].copy()
            moinhos[["_row_excel", "_date", "_type", "siat_ano", ref, "valor_oferta", "_raw_vu",
                "siat_latitude", "siat_longitude", schema.DERIVED_CONFLITO_TIPOLOGICO]].to_csv(OUT / "moinhos_registros.csv", index=False, encoding="utf-8-sig")
        for type_name in (core.TIPO_ITBI, core.TIPO_OFERTA):
            for threshold in THRESHOLDS:
                for stage, frame in stages.items():
                    vu = frame[mapping.valor] / frame[ref]
                    high = frame.loc[frame["_type"].eq(type_name) & vu.ge(threshold) & np.isfinite(vu) & frame[ref].gt(0)]
                    threshold_rows.append({"purpose": purpose, "type": type_name, "threshold_vu": threshold,
                        "stage": stage, "n": len(high), "recent_n": int(high["_date"].ge(RECENT).sum()),
                        "recent_unique_registrations": high.loc[high["_date"].ge(RECENT), "siat_inscricao"].nunique()})
        for _, row in upper.iterrows():
            exclusion_rows.append({"purpose": purpose, "row_excel": row["_row_excel"], "date": str(row["_date"].date()),
                "bairro": row["siat_bairro"], "area_m2": row[ref], "total": row[mapping.valor],
                "vu": row["_valor_unitario_original"], "upper_limit": prefilter_diag["prefilter_upper_vu"],
                "score": row["_escore_robusto_prefiltro"], "reason": row["_motivo_exclusao"]})
        item = {"purpose": purpose, "reference_area": ref, "profile": params,
                "prepared_rows": len(preparation.data), "itbi": preparation.diagnostics["n_itbi"],
                "offers": preparation.diagnostics["n_offer"], "offer_discount": preparation.discount,
                "upper_limit": prefilter_diag["prefilter_upper_vu"], "upper_excluded": len(upper),
                "upper_excluded_recent": int(upper["_date"].ge(RECENT).sum()),
                "upper_excluded_below_30000": int(upper["_valor_unitario_original"].lt(30000).sum()),
                "upper_excluded_below_30000_recent": int((upper["_valor_unitario_original"].lt(30000) & upper["_date"].ge(RECENT)).sum()),
                "exclusion_reasons": preparation.excluded_data["_motivo_exclusao"].value_counts().to_dict(),
                "conflict_policy": preparation.diagnostics.get("conflict_policy"),
                "date_kept_min": str(preparation.data["_date"].min()), "date_kept_max": str(preparation.data["_date"].max())}
        summary["purposes"].append(item)
        save_json("diagnostico.json", summary)
        log(json.dumps({k:item[k] for k in ("purpose", "prepared_rows", "upper_limit", "upper_excluded", "upper_excluded_recent", "upper_excluded_below_30000_recent")}, ensure_ascii=False))
        # Resultados já reservados da calibração; nenhum parâmetro é reajustado.
        slug = {"APARTAMENTO":"apartamento", "COBERTURA":"cobertura", "CASA / RESIDENCIA":"casa_residencia"}[purpose]
        predictions = pd.read_csv(CAL / f"{slug}_mercado/test_predictions.csv")
        baseline = predictions.loc[predictions["config"].eq("baseline") & predictions["error"].isna()].copy()
        baseline["vu_actual"] = baseline["actual"] / baseline["area"]
        if not len(baseline):
            raise ValueError(f"Teste baseline ausente: {purpose}")
        decile = baseline["actual"].quantile(.9)
        for name, subset in [("todos", baseline), ("decil_superior_valor_total", baseline.loc[baseline["actual"].ge(decile)]),
            ("vu_acima_15000", baseline.loc[baseline["vu_actual"].ge(15000)]), ("vu_acima_20000", baseline.loc[baseline["vu_actual"].ge(20000)])]:
            if len(subset):
                test_rows.append({"purpose": purpose, "segment": name, **metrics(subset["actual"], subset["predicted"]), "p90_total_cutoff": decile})
        # Dois alvos recentes por finalidade, escolhidos por VU observado; diagnóstico
        # ilustrativo. Mesma inscrição e assinatura física excluídas ANTES de preparar.
        targets = baseline.sort_values("vu_actual", ascending=False).head(2)
        for _, observed in targets.iterrows():
            row = group.loc[group["_row_excel"].eq(observed["row_excel"])].iloc[0]
            target_date = pd.Timestamp(row["_date"])
            def fingerprint(frame):
                return (frame[mapping.latitude].round(5).astype(str) + "|" + frame[mapping.longitude].round(5).astype(str)
                    + "|" + frame[mapping.area_construida].round(0).astype(str) + "|" + frame[mapping.area_privativa].round(0).astype(str))
            same_id = group["siat_inscricao"].eq(row["siat_inscricao"]) & pd.notna(row["siat_inscricao"])
            same_physical = fingerprint(group).eq(fingerprint(row.to_frame().T).iloc[0])
            train = group.loc[group["_date"].lt("2026-08-01") & ~same_id & ~same_physical].copy()
            assert train["_date"].lt(target_date).all()
            p = core.prepare_data(train, mapping, purpose, "Valor total", ref, duplicate_date_column="data_encaminhamento",
                duplicate_registration_column="siat_inscricao", duplicate_value_column="valor_oferta",
                duplicate_identifier_columns=("anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"),
                conflict_column=schema.DERIVED_CONFLITO_TIPOLOGICO, minimum_without_conflict=int(params["min_k"]))
            target = {"latitude":float(row[mapping.latitude]), "longitude":float(row[mapping.longitude]),
                      "area_construida" if ref == mapping.area_construida else "area_privativa":float(row[ref])}
            if core.is_valid_construction_year(row[mapping.ano_construcao]):
                target["ano_construcao"] = float(row[mapping.ano_construcao])
            estimate = core.estimate_knn(p, mapping, target, ref, **{k:params[k] for k in ("min_k", "max_k", "min_effective_neighbors", "similarity_weight", "distance_power", "max_individual_weight", "robust_mad_threshold")})
            neighbors = estimate.neighbors
            raw_mean = float(np.sum(neighbors["_peso_knn"] * neighbors["_valor_unitario_ajustado"]))
            upper_clipped = neighbors["_valor_unitario_ajustado"].gt(neighbors["_valor_unitario_robusto"])
            simulation_rows.append({"purpose":purpose, "target_row_excel":int(row["_row_excel"]), "date":str(target_date.date()),
                "bairro":row["siat_bairro"], "actual_vu":float(row[mapping.valor]/row[ref]), "predicted_vu":estimate.estimated_unit_value,
                "weighted_vu_before_winsor":raw_mean, "winsor_net_change_percent":100*(estimate.estimated_unit_value/raw_mean-1),
                "k":len(neighbors), "upper_clipped_n":int(upper_clipped.sum()),
                "newest_neighbor_date":str(neighbors["_date"].max().date()), "oldest_neighbor_date":str(neighbors["_date"].min().date()),
                "recent_neighbors_n":int(neighbors["_date"].ge(RECENT).sum()),
                "neighbors_vu_max":float(neighbors["_valor_unitario_ajustado"].max()),
                "robust_upper":estimate.diagnostics["robust_upper_bound"],
                "upper_prefilter":p.diagnostics["prefilter_upper_vu"]})
            selected = neighbors[["_row_excel", "_date", "siat_bairro", "_valor_unitario_ajustado", "_valor_unitario_robusto", "_peso_knn", "_distancia_geografica_km"]].copy()
            selected["purpose"] = purpose
            selected["target_row_excel"] = int(row["_row_excel"])
            simulation_neighbors.extend(selected.to_dict("records"))
            log(f"Simulação auditada: alvo linha {int(row['_row_excel'])}; {len(neighbors)} comparáveis.")
    for name, records in [("contagens_por_etapa.csv",threshold_rows), ("exclusoes_cauda_superior.csv",exclusion_rows),
        ("metricas_teste_reservado.csv",test_rows), ("simulacoes.csv",simulation_rows), ("vizinhos_simulados.csv",simulation_neighbors)]:
        pd.DataFrame(records).to_csv(OUT / name, index=False, encoding="utf-8-sig")
    save_json("diagnostico.json", summary)
    log("Auditoria concluída; planilha e parâmetros operacionais não foram alterados.")


if __name__ == "__main__":
    main()
