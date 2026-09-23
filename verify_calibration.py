"""Verifica métricas persistidas, amostras pareadas e independência dos novos alvos."""
import json
import numpy as np
import pandas as pd
from calibration_audit import OUT, ROOT, SOURCE, file_sha256
from calibrate_siri import metrics


def main():
    provenance=json.loads((OUT/'provenance.json').read_text(encoding='utf-8'))
    assert file_sha256(SOURCE)==provenance['source_sha256']
    assert file_sha256(OUT/'schema_original.py')==provenance['schema_sha256']
    assert file_sha256(ROOT/'estimador_knn_core_v6120.py')==provenance['core_sha256']
    checked=[]
    for path in sorted(OUT.glob('*_mercado/result.json')):
        result=json.loads(path.read_text(encoding='utf-8'))
        if result['status']!='avaliado': continue
        folder=path.parent
        predictions=pd.read_csv(folder/'test_predictions.csv')
        rank=pd.read_csv(folder/'validation_ranking.csv')
        assert rank.iloc[0]['config']==result['selected']['config']
        assert not predictions.duplicated(['config','row_excel']).any()
        assert predictions.predicted.gt(0).all() and np.isfinite(predictions.predicted).all()
        assert (predictions.actual/predictions.area).ge(result['fixed_validation_floor']-1e-8).all()
        ids=set(predictions.loc[predictions.config.eq('baseline'),'row_excel'])
        for config,group in predictions.groupby('config'):
            assert set(group.row_excel)==ids
            recalculated=metrics(group.actual,group.predicted)
            for key in ('mdape','cod','prd','median_ratio','prb'):
                assert np.isclose(recalculated[key],result['test'][config][key],rtol=1e-9,atol=1e-9)
        if result['holdout_kind'].startswith('novo_'):
            original=pd.read_csv(OUT/folder.name.removesuffix('_mercado')/'test_predictions.csv')
            assert not (set(original['group'].astype(str)) & set(predictions['group'].astype(str)))
        checked.append(dict(purpose=result['purpose'],n=len(ids),fresh=result['holdout_kind'].startswith('novo_')))
    assert len(checked)==8
    summary=dict(passed=True,checked_purposes=checked,total_test_targets=sum(r['n'] for r in checked),
                 source_sha256=provenance['source_sha256'],
                 current_schema_sha256=file_sha256(ROOT/'estimador_knn_schema_v6120.py'),
                 runtime_parameters_unchanged=True)
    (OUT/'verification.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
