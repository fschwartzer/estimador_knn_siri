import unittest
import numpy as np
import pandas as pd
import estimador_knn_schema_v6120 as schema


class CondominiumLandAreaTests(unittest.TestCase):
    def source(self, negotiated):
        return pd.DataFrame({
            'tipo_informacao':['Guia ITBI']*len(negotiated),
            'siat_finalidade_descricao':['TERRENO EM CONDOMINIO HORIZONTAL FECHADO']*len(negotiated),
            'siat_area_terreno':[865201.8]*len(negotiated),
            'crawler_area_terreno':negotiated,
            'valor_oferta':[300000]*len(negotiated),
            'siat_latitude':[-30]*len(negotiated),
            'siat_longitude':[-51.2]*len(negotiated)})

    def test_itbi_condominium_uses_negotiated_unit(self):
        d,info=schema.enrich_known_schemas(self.source([502.19,1419.04]))
        self.assertEqual(d[schema.DERIVED_AREA_LOTE].tolist(),[502.19,1419.04])
        self.assertTrue(d['siat_area_terreno'].eq(865201.8).all())
        self.assertIn(schema.DERIVED_REGRA_AREA_LOTE,info.added_columns)

    def test_missing_unit_does_not_fall_back_to_whole_condominium(self):
        for values in ([np.nan,0,-1,np.inf],):
            d,_=schema.enrich_known_schemas(self.source(values))
            self.assertTrue(d[schema.DERIVED_AREA_LOTE].isna().all())

    def test_other_properties_preserve_existing_area_priority(self):
        raw=self.source([502.19,600])
        raw['siat_finalidade_descricao']=['TERRENO','RESIDENCIA EM CONDOMINIO']
        d,_=schema.enrich_known_schemas(raw)
        self.assertEqual(d[schema.DERIVED_AREA_LOTE].tolist(),[865201.8,865201.8])

    def test_explicit_negotiated_area_takes_precedence(self):
        raw=self.source([502.19])
        raw['area_lote_negociada']=[510]
        d,_=schema.enrich_known_schemas(raw)
        self.assertEqual(d.loc[0,schema.DERIVED_AREA_LOTE],510)


if __name__=='__main__':
    unittest.main()
