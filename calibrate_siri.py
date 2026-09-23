"""Busca reproduzível em etapas, com confirmação temporal nunca usada no ranking.

Triagem aproximada: omite apenas o filtro local, amostra treino até 6000.
Finalistas: executa o núcleo original completo, com todo treino elegível.
Pisos são parâmetros de TREINO; o teste não é truncado por valor unitário.
"""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
import argparse
import json
import time
import numpy as np
import pandas as pd
import estimador_knn_core_v6120 as core
import estimador_knn_schema_v6120 as schema
from calibration_audit import OUT, SOURCE, file_sha256

SEED = 23092026
FOLDS = [('2025-02-01', '2025-08-01'), ('2025-08-01', '2026-02-01'),
         ('2026-02-01', '2026-08-01')]
TEST = ('2026-08-01', '2026-09-24')
PARAMS = ['min_k','max_k','min_effective_neighbors','similarity_weight',
          'distance_power','max_individual_weight','robust_mad_threshold']

def metrics(actual, predicted):
    y, p = np.asarray(actual, float), np.asarray(predicted, float)
    ok = np.isfinite(p) & np.isfinite(y) & (y > 0) & (p > 0)
    y, p = y[ok], p[ok]
    if not len(y):
        return {'n': 0, 'score': float('inf')}
    ratio = p/y
    med = np.median(ratio)
    # PRD pondera pelo VALOR TOTAL, não pelo valor unitário.
    prd = np.mean(ratio)/(p.sum()/y.sum())
    cod = np.mean(np.abs(ratio-med))/med*100
    logerr = np.abs(np.log(ratio))
    result = dict(n=len(y), mdape=float(np.median(np.abs(ratio-1))),
                  mape=float(np.mean(np.abs(ratio-1))), p90_ape=float(np.quantile(np.abs(ratio-1), .9)),
                  median_ratio=float(med), cod=float(cod), prd=float(prd),
                  mean_abs_log=float(logerr.mean()), rmse=float(np.sqrt(np.mean((p-y)**2))))
    # Critério definido antes da busca: precisão + dispersão + nível + PRD.
    result['score'] = float(logerr.mean() + .25*cod/100 + .5*abs(np.log(med)) + .5*abs(np.log(prd)))
    proxy = (y + p/med)/2
    x = np.log2(proxy)
    result['prb'] = float(np.polyfit(x, (ratio-med)/med, 1)[0]) if np.std(x)>0 and len(y)>3 else np.nan
    return result

def clean_id(series):
    return series.fillna('').astype(str).str.strip().str.replace(r'\.0$', '', regex=True).replace({'0':'','nan':'','None':''})

def load_data():
    provenance_path=OUT/'provenance.json'
    if provenance_path.exists():
        provenance=json.loads(provenance_path.read_text(encoding='utf-8'))
        digest=file_sha256(SOURCE)
        if digest!=provenance['source_sha256']:
            raise ValueError('A planilha mudou. Não reutilize os caches de uma extração diferente.')
    d = pd.read_pickle(OUT/'enriched.pkl')
    d['_purpose'] = d[schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA]
    d['_type'] = d[schema.DERIVED_TIPO_INFORMACAO].map(core.normalize_text)
    for col in ['valor_oferta','siat_latitude','siat_longitude','siat_ano', schema.DERIVED_AREA_PRIVATIVA,
                schema.DERIVED_AREA_CONSTRUIDA,schema.DERIVED_AREA_LOTE,schema.DERIVED_TESTADA]:
        d[col] = core.to_numeric(d[col])
    d['_id'] = clean_id(d['siat_inscricao'])
    # Segunda chave conservadora: unidade de características iguais no mesmo ponto.
    d['_fingerprint'] = (d['siat_latitude'].round(5).astype(str)+'|'+d['siat_longitude'].round(5).astype(str)
                         +'|'+d[schema.DERIVED_AREA_CONSTRUIDA].round(0).astype(str)
                         +'|'+d[schema.DERIVED_AREA_PRIVATIVA].round(0).astype(str))
    d['_group'] = d['_id'].where(d['_id'].ne(''), d['_fingerprint'])
    d['_tile'] = (np.floor(d['siat_latitude']*111.195).astype('Int64').astype(str)+'|'
                  +np.floor(d['siat_longitude']*96.3).astype('Int64').astype(str))
    keep = list(dict.fromkeys(['_row_excel','_purpose','_type','_date','_id','_group','_fingerprint','_tile',
        'siat_inscricao','siat_bairro','siat_latitude','siat_longitude','siat_ano','valor_oferta','data_encaminhamento',
        'anuncio_website','imobiliaria_codigo_anuncio','idf_registro',schema.DERIVED_TIPO_INFORMACAO,
        schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA,schema.DERIVED_CONFLITO_TIPOLOGICO,
        schema.DERIVED_AREA_PRIVATIVA,schema.DERIVED_AREA_CONSTRUIDA,schema.DERIVED_AREA_LOTE,schema.DERIVED_TESTADA]))
    return d[keep]

def mapping():
    return core.ColumnMapping(schema.DERIVED_TIPO_INFORMACAO,schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA,
          'valor_oferta',schema.DERIVED_AREA_CONSTRUIDA,schema.DERIVED_AREA_PRIVATIVA,
          'siat_latitude','siat_longitude',schema.DERIVED_AREA_LOTE,schema.DERIVED_TESTADA,'siat_ano')

def reference(purpose):
    preference = schema.reference_area_preference(purpose)
    return (schema.DERIVED_AREA_LOTE if preference=='terreno' else
            schema.DERIVED_AREA_CONSTRUIDA if preference=='construida' else schema.DERIVED_AREA_PRIVATIVA)

def eligible(d, ref):
    mask = (d['_type'].eq(core.TIPO_ITBI) & d['_date'].notna() & d['valor_oferta'].gt(1)
            & np.isfinite(d['valor_oferta']) & d[ref].gt(0) & np.isfinite(d[ref])
            & d['siat_latitude'].between(-31,-29) & d['siat_longitude'].between(-52,-50))
    if ref==schema.DERIVED_AREA_LOTE:
        mask &= d[schema.DERIVED_TESTADA].gt(0) & np.isfinite(d[schema.DERIVED_TESTADA])
    if '_validation_floor' in d:
        # Universo operacional FIXO para todos os candidatos, conforme usuário.
        # Nunca usar o piso candidato para escolher quais alvos serão avaliados.
        mask &= (d['valor_oferta']/d[ref]).ge(d['_validation_floor'])
    return d.loc[mask].sort_values(['_date','_row_excel']).drop_duplicates('_group', keep='last')

def split(d, start, end, ref, size):
    test = eligible(d.loc[d['_date'].ge(start) & d['_date'].lt(end)], ref)
    if start==TEST[0] and '_exclude_final_target' in test:
        test=test.loc[~test['_exclude_final_target']]
    if start==TEST[0] and '_frozen_final_target' in test:
        test=test.loc[test['_frozen_final_target']]
    if len(test)>size:
        test = test.sample(size, random_state=SEED)
    # Retira identidade ANTES de preparação/desconto/padronização, em todos os pisos.
    train = d.loc[d['_date'].lt(start) & d['_date'].notna()
                  & d['_type'].isin([core.TIPO_ITBI, core.TIPO_OFERTA])].copy()
    train = train.loc[~train['_id'].isin(set(test['_id'])-{''})
                      & ~train['_fingerprint'].isin(set(test['_fingerprint']))]
    assert train['_date'].lt(start).all()
    assert not (set(train['_id']) & (set(test['_id'])-{''}))
    assert not (set(train['_fingerprint']) & set(test['_fingerprint']))
    return train, test

def prepare(train, purpose, ref, floor):
    key = core.normalize_text(purpose)
    old = core.PURPOSE_UNIT_VALUE_FLOORS.get(key)
    try:
        core.PURPOSE_UNIT_VALUE_FLOORS[key] = floor
        p = core.prepare_data(train, mapping(), purpose, 'Valor total', ref,
            duplicate_date_column='data_encaminhamento', duplicate_registration_column='siat_inscricao',
            duplicate_value_column='valor_oferta',
            duplicate_identifier_columns=('anuncio_website','imobiliaria_codigo_anuncio','idf_registro'),
            conflict_column=schema.DERIVED_CONFLITO_TIPOLOGICO, minimum_without_conflict=48)
    finally:
        if old is None: core.PURPOSE_UNIT_VALUE_FLOORS.pop(key, None)
        else: core.PURPOSE_UNIT_VALUE_FLOORS[key] = old
    # Remove somente colunas não utilizadas pelos cálculos, reduzindo cópias.
    cols = [ref,'siat_ano','siat_latitude','siat_longitude',schema.DERIVED_AREA_LOTE,
            schema.DERIVED_TESTADA,'_valor_unitario_ajustado','_row_excel','_tile']
    return replace(p, data=p.data[list(dict.fromkeys(cols))])

def target_for(row, ref, purpose):
    t = {'latitude':float(row['siat_latitude']), 'longitude':float(row['siat_longitude']),ref:float(row[ref])}
    key = {schema.DERIVED_AREA_PRIVATIVA:'area_privativa',schema.DERIVED_AREA_CONSTRUIDA:'area_construida',
           schema.DERIVED_AREA_LOTE:'siat_area_total_lote'}[ref]
    t[key] = float(row[ref])
    if ref==schema.DERIVED_AREA_LOTE:
        t['testada'] = float(row[schema.DERIVED_TESTADA])
    else:
        if core.is_valid_construction_year(row['siat_ano']):
            t['ano_construcao'] = float(row['siat_ano'])
        if purpose in {'CASA / RESIDÊNCIA','GALPÃO / DEPÓSITO','IMÓVEL COMERCIAL'} and pd.notna(row[schema.DERIVED_AREA_LOTE]) and row[schema.DERIVED_AREA_LOTE]>0:
            t['siat_area_total_lote'] = float(row[schema.DERIVED_AREA_LOTE])
    return t

def config_grid(purpose):
    base = {k:v for k,v in core.calibrated_parameters_for_purpose(purpose).items() if k in PARAMS}
    floor = core.PURPOSE_UNIT_VALUE_FLOORS.get(core.normalize_text(purpose),0)
    original = dict(base, floor=floor, config='baseline')
    configs = [original]
    ksets = [(k,k,max(2,k*.8)) for k in (5,8,12,16,24,32,48)] + [(5,15,5),(8,24,8),(12,36,12),(16,48,16)]
    ksets.append((base['min_k'],base['max_k'],base['min_effective_neighbors']))
    for f in sorted(set([0.,floor*.5,floor,floor*1.5,floor*2])):
        for weight in sorted(set([.1,.25,.45,.6,.75,.9,base['similarity_weight']])):
            for mink,maxk,eff in ksets:
                c = dict(base,min_k=mink,max_k=maxk,min_effective_neighbors=eff,similarity_weight=weight,floor=f)
                c['config'] = f'f{f:g}_w{weight:g}_k{mink}-{maxk}_e{eff:g}'
                if all(c[x]==original[x] for x in PARAMS+['floor']): continue
                configs.append(c)
    return configs

def quick_predict(dist, geo, values, c):
    order = np.argsort(dist,kind='mergesort')[:c['max_k']]
    if len(order)<2: return np.nan
    low = min(c['min_k'],len(order))
    for k in range(low,len(order)+1):
        ix=order[:k]
        g=geo[ix]*1000
        bonus=np.where(g<=30,2.,np.where(g<=50,1+(50-g)/20,1.))
        raw=bonus/np.power(dist[ix]+1e-9,c['distance_power'])
        weights,_=core._cap_and_normalize_weights(raw,c['max_individual_weight'])
        if 1/(weights@weights)>=c['min_effective_neighbors']: break
    return core._robust_weighted_mean(values[ix],weights,c['robust_mad_threshold'])[0]

def screen(d,purpose,ref,configs):
    records=[]
    for fold,(start,end) in enumerate(FOLDS):
        train,test=split(d,start,end,ref,24)
        if len(test)<8 or len(train)<50: continue
        # Triagem apenas. Finalistas são reavaliados usando todos os comparáveis.
        if len(train)>6000: train=train.sample(6000,random_state=SEED)
        for floor in sorted({c['floor'] for c in configs}):
            p=prepare(train,purpose,ref,floor)
            for idx,row in test.iterrows():
                target=target_for(row,ref,purpose)
                features,_=core._resolve_features(mapping(),target,ref==schema.DERIVED_AREA_LOTE)
                candidates,_=core._valid_candidates(p.data,mapping(),features,True)
                if len(candidates)<2: continue
                _,attr,geo,scale=core._distance_profile(candidates,mapping(),features,target,.5,True)
                values=candidates['_valor_unitario_ajustado'].to_numpy(float)
                for c in configs:
                    if c['floor']!=floor: continue
                    w=c['similarity_weight']
                    dist=np.sqrt(w*attr**2+(1-w)*(geo/scale)**2)
                    pred=quick_predict(dist,geo,values,c)*row[ref]
                    records.append((c['config'],fold,float(row['valor_oferta']),pred))
    frame=pd.DataFrame(records,columns=['config','fold','actual','predicted'])
    scores=[]
    for cid,g in frame.groupby('config'):
        ms=metrics(g.actual,g.predicted)
        scores.append(dict(config=cid,**ms))
    return pd.DataFrame(scores).sort_values('score') if scores else pd.DataFrame()

def evaluate(train,test,purpose,ref,configs,label,spatial=False):
    records=[]
    for floor in sorted({c['floor'] for c in configs}):
        # Leave-cell-out stress reprepares each training set, including its discount.
        groups=test.groupby('_tile') if spatial else [('all',test)]
        for tile, cases in groups:
            tr=train.loc[train['_tile'].ne(tile)] if spatial else train
            p=prepare(tr,purpose,ref,floor)
            for c in configs:
                if c['floor']!=floor: continue
                for idx,row in cases.iterrows():
                    error=''
                    try:
                        result=core.estimate_knn(p,mapping(),target_for(row,ref,purpose),ref,
                            territorial=ref==schema.DERIVED_AREA_LOTE,**{k:c[k] for k in PARAMS})
                        pred=result.estimated_total_value
                        k=result.diagnostics['k_used']
                        eff=result.effective_neighbors
                    except (ValueError,RuntimeError) as exc:
                        pred,k,eff=np.nan,0,0
                        error=str(exc)
                    records.append(dict(purpose=purpose,config=c['config'],fold=label,row_excel=int(row['_row_excel']),
                        date=str(row['_date'].date()),group=row['_group'],tile=row['_tile'],bairro=row['siat_bairro'],
                        area=float(row[ref]),actual=float(row['valor_oferta']),predicted=pred,k=k,effective=eff,
                        floor=floor,n_train=len(p.data),discount=p.discount,error=error))
    return pd.DataFrame(records)

def bootstrap_pair(frame,first,second,reps=1000):
    p=frame.pivot(index='row_excel',columns='config',values='predicted')
    y=frame.drop_duplicates('row_excel').set_index('row_excel').actual.reindex(p.index)
    good=p[[first,second]].notna().all(axis=1)
    p,y=p.loc[good],y.loc[good]
    if len(y)<10: return {}
    # Agrupamento por célula de aproximadamente 1 km, para dependência espacial.
    tiles=frame.drop_duplicates('row_excel').set_index('row_excel').tile.reindex(p.index)
    groups=[np.flatnonzero(tiles.to_numpy()==t) for t in tiles.unique()]
    rng=np.random.default_rng(SEED)
    gains=[]
    a=np.abs(p[first].to_numpy()/y.to_numpy()-1)
    b=np.abs(p[second].to_numpy()/y.to_numpy()-1)
    for _ in range(reps):
        ix=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        gains.append(np.median(a[ix])-np.median(b[ix]))
    return dict(n_pairs=len(y),n_spatial_blocks=len(groups),mdape_gain=float(np.median(a)-np.median(b)),
                gain_ci95_low=float(np.quantile(gains,.025)),gain_ci95_high=float(np.quantile(gains,.975)))

def run_purpose(purpose,d,output_suffix=''):
    begun=time.time()
    slug=core.normalize_text(purpose).replace(' / ','_').replace(' ','_')
    folder=OUT/(slug+output_suffix)
    folder.mkdir(exist_ok=True)
    ref=reference(purpose)
    counts={f'{s}_{e}':len(eligible(d.loc[d['_date'].ge(s)&d['_date'].lt(e)],ref)) for s,e in FOLDS+[TEST]}
    result=dict(purpose=purpose,reference_area=ref,counts=counts,output_suffix=output_suffix)
    if '_validation_floor' in d:
        result['fixed_validation_floor']=float(d['_validation_floor'].iloc[0])
        result['holdout_kind']=str(d['_holdout_kind'].iloc[0])
    if counts[f'{TEST[0]}_{TEST[1]}']<30 or sum(list(counts.values())[:3])<90:
        result.update(status='amostra_insuficiente',baseline=config_grid(purpose)[0])
        (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result
    configs=config_grid(purpose)
    rank=screen(d,purpose,ref,configs)
    rank.to_csv(folder/'screening.csv',index=False)
    if rank.empty: raise RuntimeError(f'Sem previsões na triagem: {purpose}')
    # Diversidade dos finalistas: dois melhores globais + melhor por piso.
    byid={c['config']:c for c in configs}
    ids=['baseline']+rank.config.head(2).tolist()
    for floor in sorted({c['floor'] for c in configs}):
        ids += rank.loc[rank.config.map(lambda x:byid[x]['floor']==floor),'config'].head(1).tolist()
    finalists=[byid[cid] for cid in dict.fromkeys(ids)]
    tuning=[]
    for fold,(start,end) in enumerate(FOLDS):
        train,test=split(d,start,end,ref,90)
        if len(test)<8 or len(train)<50: continue
        tuning.append(evaluate(train,test,purpose,ref,finalists,f'validacao_{fold+1}'))
    tuning=pd.concat(tuning,ignore_index=True)
    tuning.to_csv(folder/'validation_predictions.csv',index=False)
    scores=[]
    for cid,g in tuning.groupby('config'):
        m=metrics(g.actual,g.predicted)
        m['coverage']=float(g.predicted.notna().mean())
        # Falhas não podem melhorar o ranking removendo casos difíceis.
        m['score'] += 5*(1-m['coverage'])
        fold_scores=[metrics(x.actual,x.predicted)['score'] for _,x in g.groupby('fold')]
        m['selection_score']=float(np.mean(fold_scores)+.25*np.std(fold_scores)+5*(1-m['coverage']))
        scores.append(dict(config=cid,**m))
    scores=pd.DataFrame(scores).sort_values('selection_score')
    scores.to_csv(folder/'validation_ranking.csv',index=False)
    winner=byid[scores.iloc[0]['config']]
    # Congelamento dos finalistas antes de abrir o teste reservado.
    (folder/'locked_selection.json').write_text(json.dumps(winner,indent=2),encoding='utf-8')
    chosen=[byid['baseline']]+([] if winner['config']=='baseline' else [winner])
    train,test=split(d,*TEST,ref,350)
    holdout=evaluate(train,test,purpose,ref,chosen,'teste_reservado')
    holdout.to_csv(folder/'test_predictions.csv',index=False)
    spatial=evaluate(train,test.sample(min(60,len(test)),random_state=SEED),purpose,ref,chosen,'teste_espacial',True)
    spatial.to_csv(folder/'spatial_predictions.csv',index=False)
    result.update(status='avaliado',grid_count=len(configs),finalists=len(finalists),baseline=byid['baseline'],selected=winner,
         validation=scores.to_dict('records'),test={cid:metrics(g.actual,g.predicted) for cid,g in holdout.groupby('config')},
         spatial={cid:metrics(g.actual,g.predicted) for cid,g in spatial.groupby('config')},
         confidence=bootstrap_pair(holdout,'baseline',winner['config']) if winner['config']!='baseline' else {},
         runtime_seconds=round(time.time()-begun,1))
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--purpose')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--corrected-land',action='store_true',
                        help='Rodada exploratória separada com área negociada do condomínio.')
    parser.add_argument('--market',action='store_true',
                        help='Universo operacional fixo pelos pisos atuais; conforme esclarecimento do usuário.')
    args=parser.parse_args()
    d=load_data()
    if args.market:
        previous_targets={}
        for purpose,g in d.groupby('_purpose'):
            if purpose:
                _,previous=split(g,*TEST,reference(purpose),350)
                previous_targets[purpose]=set(previous['_group'])
        raw=pd.read_pickle(OUT/'source_selected.pkl')
        land_indices=d.index[d['_purpose'].eq('TERRENO')]
        corrected,_=schema.enrich_known_schemas(raw.loc[land_indices])
        d.loc[land_indices,schema.DERIVED_AREA_LOTE]=corrected[schema.DERIVED_AREA_LOTE]
        del raw,corrected
        d['_validation_floor']=d['_purpose'].map(lambda p:core.PURPOSE_UNIT_VALUE_FLOORS.get(core.normalize_text(p),0.))
        d['_exclude_final_target']=False
        d['_holdout_kind']='reutilizado_condicionado_ao_piso_fixo'
        for purpose,g in d.groupby('_purpose'):
            if not purpose: continue
            available=eligible(g.loc[g['_date'].ge(TEST[0])],reference(purpose))
            unseen=available.loc[~available['_group'].isin(previous_targets[purpose])]
            if len(unseen)>=50:
                d.loc[g.index,'_exclude_final_target']=g['_group'].isin(previous_targets[purpose])
                d.loc[g.index,'_holdout_kind']='novo_alvo_nao_avaliado_na_rodada_bruta'
        frozen_path=OUT/'market_holdout_targets.json'
        if frozen_path.exists():
            frozen=json.loads(frozen_path.read_text(encoding='utf-8'))
            d['_frozen_final_target']=False
            for purpose,rows in frozen.items():
                selected=d['_purpose'].eq(purpose)&d['_row_excel'].isin(rows)
                d.loc[selected,'_frozen_final_target']=True
    if args.corrected_land:
        d=d.loc[d['_purpose'].eq('TERRENO')].copy()
        raw=pd.read_pickle(OUT/'source_selected.pkl').loc[d.index]
        corrected,info=schema.enrich_known_schemas(raw)
        before=d[schema.DERIVED_AREA_LOTE].copy()
        d[schema.DERIVED_AREA_LOTE]=corrected[schema.DERIVED_AREA_LOTE]
        changed=~np.isclose(before,d[schema.DERIVED_AREA_LOTE],equal_nan=True)
        audit=corrected.loc[changed,['_row_excel','siat_finalidade_descricao','siat_area_terreno',
                                     'crawler_area_terreno',schema.DERIVED_AREA_LOTE,schema.DERIVED_REGRA_AREA_LOTE]]
        audit.to_csv(OUT/'land_area_corrections.csv',index=False)
        print(f'Áreas de terreno alteradas: {int(changed.sum())}',flush=True)
        result=run_purpose('TERRENO',d,'_area_negociada')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        return
    jobs=[]
    results=[]
    for purpose,g in d.groupby('_purpose'):
        if not purpose or (args.purpose and purpose!=args.purpose): continue
        slug=core.normalize_text(purpose).replace(' / ','_').replace(' ','_')
        suffix='_mercado' if args.market else ''
        done=OUT/(slug+suffix)/'result.json'
        if args.resume and done.exists():
            results.append(json.loads(done.read_text(encoding='utf-8')))
            continue
        jobs.append((purpose,g))
    # Categorias menores primeiro: resultados parciais e diagnóstico rápido.
    jobs.sort(key=lambda item:len(item[1]))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        future_map={pool.submit(run_purpose,p,g,'_mercado' if args.market else ''):p for p,g in jobs}
        for future in as_completed(future_map):
            p=future_map[future]
            try:
                r=future.result()
                results.append(r)
                print(json.dumps({'purpose':p,'status':r['status'],'selected':r.get('selected'),
                     'test':r.get('test'),'confidence':r.get('confidence')},ensure_ascii=False),flush=True)
            except Exception as exc:
                print(f'ERRO {p}: {exc!r}',flush=True)
                raise
    if not args.purpose:
        (OUT/('results_market.json' if args.market else 'results.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    main()
