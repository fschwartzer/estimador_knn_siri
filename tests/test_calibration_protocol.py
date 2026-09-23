"""Invariantes que impedem métricas otimistas na calibração temporal."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import calibrate_siri as cal


class CalibrationProtocolTests(unittest.TestCase):
    def test_prd_uses_total_prices(self):
        result = cal.metrics([100, 1000], [150, 800])
        self.assertAlmostEqual(result['prd'], 1.15 / (950 / 1100))
        self.assertAlmostEqual(result['median_ratio'], 1.15)

    def test_temporal_split_purges_all_property_observations(self):
        ref = cal.schema.DERIVED_AREA_PRIVATIVA
        d = pd.DataFrame({
            '_date': pd.to_datetime(['2025-01-01','2025-01-02','2025-01-03','2025-02-10','2025-03-01']),
            '_type': [cal.core.TIPO_ITBI]*5, '_id':['same','other','third','same','future'],
            '_fingerprint':['a','b','c','a','e'], '_group':['same','other','third','same','future'],
            '_row_excel':[2,3,4,5,6], 'valor_oferta':[1000,2000,3000,2,4000],
            ref:[100]*5, 'siat_latitude':[-30.0]*5,'siat_longitude':[-51.2]*5})
        train,test=cal.split(d,'2025-02-01','2025-03-01',ref,50)
        self.assertEqual(set(train['_id']),{'other','third'})
        self.assertEqual(set(test['_id']),{'same'})
        # Preço muito baixo continua no teste: pisos não podem facilitar a prova.
        self.assertEqual(test.iloc[0]['valor_oferta'],2)

    def test_screening_matches_core_without_local_filter(self):
        core=cal.core
        m=core.ColumnMapping('type','purpose','price',None,'area','lat','lon',None,None)
        d=pd.DataFrame({'area':np.linspace(50,200,60),'lat':np.linspace(-30.01,-30.03,60),
                        'lon':np.linspace(-51.15,-51.2,60),'_valor_unitario_ajustado':np.linspace(2000,7000,60)})
        p=core.PreparationResult(d,0,{'purpose':'APARTAMENTO'},pd.DataFrame(),pd.DataFrame())
        target={'area_privativa':100,'latitude':-30.02,'longitude':-51.17}
        params={k:v for k,v in core.calibrated_parameters_for_purpose('APARTAMENTO').items() if k in cal.PARAMS}
        features,_=core._resolve_features(m,target,False)
        dist,_,geo,_=core._distance_profile(d,m,features,target,params['similarity_weight'])
        expected=cal.quick_predict(dist,geo,d['_valor_unitario_ajustado'].to_numpy(),params)
        with patch.object(core,'_local_lower_tail_filter',return_value=(d,pd.DataFrame(),{})):
            actual=core.estimate_knn(p,m,target,'area',**params).estimated_unit_value
        self.assertAlmostEqual(expected,actual,places=9)

    def test_operational_floor_is_fixed_and_does_not_filter_training(self):
        ref=cal.schema.DERIVED_AREA_PRIVATIVA
        d=pd.DataFrame({'_date':pd.to_datetime(['2025-01-01','2025-02-10','2025-02-11']),
            '_type':[cal.core.TIPO_ITBI]*3,'_id':['train','low','market'],
            '_fingerprint':['a','b','c'],'_group':['train','low','market'],'_row_excel':[2,3,4],
            'valor_oferta':[2,2,200000],ref:[100]*3,'siat_latitude':[-30.]*3,
            'siat_longitude':[-51.2]*3,'_validation_floor':[1200.]*3})
        train,test=cal.split(d,'2025-02-01','2025-03-01',ref,50)
        self.assertEqual(test['_id'].tolist(),['market'])
        # O treino será filtrado separadamente pelo piso candidato na preparação.
        self.assertEqual(train['valor_oferta'].tolist(),[2])


if __name__=='__main__':
    unittest.main()
