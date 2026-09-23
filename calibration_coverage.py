"""Contagens do universo operacional; cortes fixos, independentes do candidato."""
import pandas as pd
import numpy as np
import calibrate_siri as cal
from calibration_audit import OUT

def main():
    d=cal.load_data()
    raw=pd.read_pickle(OUT/'source_selected.pkl')
    land=d.index[d['_purpose'].eq('TERRENO')]
    enriched,_=cal.schema.enrich_known_schemas(raw.loc[land])
    d.loc[land,cal.schema.DERIVED_AREA_LOTE]=enriched[cal.schema.DERIVED_AREA_LOTE]
    rows=[]
    for purpose,g in d.groupby('_purpose'):
        if not purpose: continue
        ref=cal.reference(purpose)
        piso=cal.core.PURPOSE_UNIT_VALUE_FLOORS.get(cal.core.normalize_text(purpose),0)
        for label,(start,end) in [('tres_anos',('2023-09-23','2026-09-24')),('teste',cal.TEST)]:
            x=g.loc[g['_date'].ge(start)&g['_date'].lt(end)&g['_type'].eq(cal.core.TIPO_ITBI)].copy()
            before=cal.eligible(x,ref)
            x['_validation_floor']=piso
            after=cal.eligible(x,ref)
            rows.append(dict(finalidade=purpose,periodo=label,piso_fixo=piso,linhas_itbi=len(x),
                area_ausente_ou_invalida=int((~np.isfinite(x[ref])|x[ref].le(0)).sum()),
                coordenada_fora_janela=int((~x['siat_latitude'].between(-31,-29)|~x['siat_longitude'].between(-52,-50)).sum()),
                imoveis_elegiveis_antes_piso=len(before),imoveis_elegiveis_apos_piso=len(after),
                casos_antes_abaixo_piso=int((before.valor_oferta/before[ref]).lt(piso).sum())))
    pd.DataFrame(rows).to_csv(OUT/'cobertura_universo_operacional.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).query("periodo == 'teste'").to_string(index=False))

if __name__=='__main__':
    main()
