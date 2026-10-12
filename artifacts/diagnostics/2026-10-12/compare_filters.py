"""Comparação pareada descritiva; não recalibra nem usa teste no preparo.

Os alvos do teste antigo já foram examinados. Esta rodada é sensibilidade,
não confirmação independente. Semente e regra de amostragem são fixas.
"""
from pathlib import Path
import importlib.util
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import estimador_knn_core_v6120 as after
import estimador_knn_schema_v6120 as schema
from calibrate_siri import metrics, clean_id
from calibration_audit import file_sha256, SOURCE

OUT = Path(__file__).resolve().parent
CAL = ROOT / "artifacts/calibration/2026-09-23"
spec = importlib.util.spec_from_file_location("vera_before_comparison", OUT / "core_before.py")
before = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = before
spec.loader.exec_module(before)


def main():
    provenance = json.loads((CAL / "provenance.json").read_text(encoding="utf-8"))
    if file_sha256(SOURCE) != provenance["source_sha256"]:
        raise ValueError("Fonte incompatível com o cache.")
    d = pd.read_pickle(CAL / "enriched.pkl")
    m = after.ColumnMapping(schema.DERIVED_TIPO_INFORMACAO, schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA,
        "valor_oferta", schema.DERIVED_AREA_CONSTRUIDA, schema.DERIVED_AREA_PRIVATIVA,
        "siat_latitude", "siat_longitude", schema.DERIVED_AREA_LOTE, schema.DERIVED_TESTADA, "siat_ano")
    columns = ["_row_excel", "_date", "data_encaminhamento", "siat_inscricao", "siat_bairro", "anuncio_website",
        "imobiliaria_codigo_anuncio", "idf_registro", schema.DERIVED_CONFLITO_TIPOLOGICO,
        m.tipo_informacao, m.finalidade_oferta, m.valor, m.area_construida, m.area_privativa,
        m.latitude, m.longitude, m.siat_area_total_lote, m.testada, m.ano_construcao]
    d = d[columns].copy()
    d["_purpose"] = d[m.finalidade_oferta].map(after.normalize_text)
    for col in (m.valor, m.area_construida, m.area_privativa, m.latitude, m.longitude,
                m.siat_area_total_lote, m.testada, m.ano_construcao):
        d[col] = after.to_numeric(d[col])
    d["_id"] = clean_id(d["siat_inscricao"])
    d["_fingerprint"] = (d[m.latitude].round(5).astype(str) + "|" + d[m.longitude].round(5).astype(str)
        + "|" + d[m.area_construida].round(0).astype(str) + "|" + d[m.area_privativa].round(0).astype(str))
    rows, stages, neighborhood, geographic = [], [], [], []
    for purpose, slug, count in [("APARTAMENTO", "apartamento", 40), ("COBERTURA", "cobertura", 20),
                                 ("CASA / RESIDÊNCIA", "casa_residencia", 30)]:
        print(f"Comparando {purpose}, amostra temporal fixa.", flush=True)
        group = d.loc[d["_purpose"].eq(after.normalize_text(purpose))].copy()
        if group.empty:
            raise ValueError(purpose)
        ref = m.area_construida if schema.reference_area_preference(purpose) == "construida" else m.area_privativa
        params = {k:v for k,v in after.calibrated_parameters_for_purpose(purpose).items()
            if k in ("min_k", "max_k", "min_effective_neighbors", "similarity_weight", "distance_power", "max_individual_weight", "robust_mad_threshold")}
        old_predictions = pd.read_csv(CAL / f"{slug}_mercado/test_predictions.csv")
        eligible = old_predictions.loc[old_predictions["config"].eq("baseline") & old_predictions["error"].isna()].copy()
        sample = eligible.sample(min(count, len(eligible)), random_state=12102026)
        high = eligible.sort_values("actual", ascending=False).head(3)
        targets = group.loc[group["_row_excel"].isin(set(sample["row_excel"]) | set(high["row_excel"]))].copy()
        targets["actual_total_decile"] = np.minimum(10, (np.searchsorted(
            eligible["actual"].quantile(np.arange(.1,1,.1)).to_numpy(), targets[m.valor], side="right") + 1))
        blocked_ids = set(targets["_id"]) - {""}
        blocked_fingerprints = set(targets["_fingerprint"])
        train = group.loc[group["_date"].lt("2026-08-01") & ~group["_id"].isin(blocked_ids)
            & ~group["_fingerprint"].isin(blocked_fingerprints)].copy()
        assert train["_date"].lt("2026-08-01").all()
        assert not set(train["_id"]) & blocked_ids
        assert not set(train["_fingerprint"]) & blocked_fingerprints
        for version, engine in [("antes", before), ("depois", after)]:
            preparation = engine.prepare_data(train, m, purpose, "Valor total", ref,
                duplicate_date_column="data_encaminhamento", duplicate_registration_column="siat_inscricao",
                duplicate_value_column="valor_oferta", duplicate_identifier_columns=("anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"),
                conflict_column=schema.DERIVED_CONFLITO_TIPOLOGICO, minimum_without_conflict=int(params["min_k"]))
            stages.append({"purpose":purpose, "version":version, "train_rows":len(train), "prepared":len(preparation.data),
                "upper_effective":preparation.diagnostics.get("prefilter_effective_upper_vu",preparation.diagnostics["prefilter_upper_vu"]),
                "statistical_excluded":preparation.diagnostics["prefilter_statistical_excluded"],
                "high_15k_30k":int(preparation.data["_valor_unitario_original"].between(15000,30000).sum()),
                "offers_above_1million_vu":int(((preparation.data["_valor_unitario_original"]>1e6) & preparation.data["_tipo_norm"].eq(engine.TIPO_OFERTA)).sum())})
            # Cobertura operacional com a base completa, fora da comparação temporal.
            if purpose == "APARTAMENTO":
                local = group.loc[group["siat_bairro"].map(engine.normalize_text).isin(["moinhos vento", "moinhos de vento"])]
                full = engine.prepare_data(group, m, purpose, "Valor total", ref,
                    duplicate_date_column="data_encaminhamento", duplicate_registration_column="siat_inscricao",
                    duplicate_value_column="valor_oferta", duplicate_identifier_columns=("anuncio_website", "imobiliaria_codigo_anuncio", "idf_registro"),
                    conflict_column=schema.DERIVED_CONFLITO_TIPOLOGICO, minimum_without_conflict=int(params["min_k"]))
                kept = full.data.loc[full.data["siat_bairro"].map(engine.normalize_text).isin(["moinhos vento", "moinhos de vento"])]
                for stage, frame in [("bruto",local),("preparado",kept)]:
                    for year, selected in frame.groupby(m.ano_construcao,dropna=False):
                        coords = selected[m.latitude].between(-90,90) & selected[m.longitude].between(-180,180)
                        neighborhood.append({"version":version,"stage":stage,"year":year,"n":len(selected),
                            "coordinate_valid_n":int(coords.sum()), "vu_15k_30k_n":int((selected[m.valor]/selected[ref]).between(15000,30000).sum())})
            for _, row in targets.iterrows():
                target = {"latitude":float(row[m.latitude]), "longitude":float(row[m.longitude]),
                    "area_construida" if ref==m.area_construida else "area_privativa":float(row[ref])}
                if engine.is_valid_construction_year(row[m.ano_construcao]):
                    target["ano_construcao"] = float(row[m.ano_construcao])
                if purpose == "CASA / RESIDÊNCIA" and pd.notna(row[m.siat_area_total_lote]) and row[m.siat_area_total_lote]>0:
                    target["siat_area_total_lote"] = float(row[m.siat_area_total_lote])
                try:
                    result = engine.estimate_knn(preparation,m,target,ref,**params)
                    predicted = result.estimated_total_value
                    error = ""
                    k = result.diagnostics["k_used"]
                except ValueError as exc:
                    predicted, k, error = np.nan, 0, str(exc)
                rows.append({"purpose":purpose,"version":version,"row_excel":int(row["_row_excel"]),
                    "date":str(row["_date"].date()),"bairro":row["siat_bairro"],"actual":float(row[m.valor]),
                    "actual_vu":float(row[m.valor]/row[ref]),"predicted":predicted,
                    "decile":int(row["actual_total_decile"]),"k":k,"error":error})
            print(f"{version}: {len(preparation.data):,} comparáveis preparados; {len(targets)} alvos.",flush=True)
    predictions = pd.DataFrame(rows)
    comparisons = []
    for (purpose,version), g in predictions.groupby(["purpose","version"]):
        for segment, s in [("todos",g), ("decil_superior",g.loc[g["decile"].eq(10)]),
            ("vu_15k_30k",g.loc[g["actual_vu"].between(15000,30000)])]:
            if len(s):
                comparisons.append({"purpose":purpose,"version":version,"segment":segment,
                    "attempted":len(s),"failures":int(s["predicted"].isna().sum()),**metrics(s["actual"],s["predicted"])})
        for bairro, s in g.groupby("bairro"):
            if len(s)>=5:
                geographic.append({"purpose":purpose,"version":version,"bairro":bairro,**metrics(s["actual"],s["predicted"])})
    for name, content in [("comparacao_previsoes.csv",predictions), ("comparacao_metricas.csv",pd.DataFrame(comparisons)),
        ("comparacao_preparacao.csv",pd.DataFrame(stages)), ("comparacao_moinhos.csv",pd.DataFrame(neighborhood)),
        ("comparacao_espacial.csv",pd.DataFrame(geographic))]:
        content.to_csv(OUT/name,index=False,encoding="utf-8-sig")
    manifest = {"source_sha256":provenance["source_sha256"],"before_sha256":file_sha256(OUT/"core_before.py"),
        "after_sha256":file_sha256(ROOT/"estimador_knn_core_v6120.py"),"seed":12102026,
        "train_before":"2026-08-01","n_pairs":len(predictions)//2,
        "purpose":"sensibilidade no teste já examinado; sem recalibração; identidade bloqueada antes do preparo"}
    (OUT/"comparacao_proveniencia.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(pd.DataFrame(comparisons)[["purpose","version","segment","n","median_ratio","cod","prd"]].to_string(index=False),flush=True)


if __name__ == "__main__":
    main()
