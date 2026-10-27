import unittest

import numpy as np
import pandas as pd

import estimador_knn_schema_v6120 as schema


def export_frame(**overrides):
    values = {
        "fonteTransacao": ["Oferta", "Guia ITBI"],
        "finalidadeNmeSiat": ["Gleba", "Gleba"],
        "finalidadeNmeCrawlerSiri": ["Casa", ""],
        "numInscricao": [123, 456],
        "numRegistroCrawler": [789, None],
        "valorOfertaCrawler": [500000, None],
        "valorOfertaPmi": [510000, 200000],
        "valorGuiaTotalDeclarado": [None, 200000],
        "valorGuiaTotalAtribuido": [None, 900000],
        "guiaAreaTerrTransmitida": [None, 100],
        "guiaPercentualGlobalTransmitido": [None, 25],
        "areaTerrLoteFiscalSiat": [600, 400],
        "areaTerrLoteFiscalPmi": [None, 400],
        "acoTotalCrawler": [120, None],
        "acoPrivativaCrawler": [100, None],
        "endLatitudeCrawler": [-30.03, None],
        "endLongitudeCrawler": [-51.23, None],
        "endLatitudePmi": [-30.04, -30.05],
        "endLongitudePmi": [-51.24, -51.25],
        "endLogradouroNmeCrawler": ["Rua de Teste", None],
        "crawlerNumero": [None, None],
        "endLogradouroNmePmi": ["Outra Rua", "Rua Sintética"],
        "endLogradouroNumPmi": [20, 30],
        "dataEncaminhaCrawler": ["01/01/2026", None],
        "dataEncaminhaPmi": ["02/01/2026", "03/01/2026"],
    }
    values.update(overrides)
    return pd.DataFrame(values)


class SiriExportTests(unittest.TestCase):
    def test_original_columns_preserved_and_categories_and_areas_recognized(self):
        original = export_frame()
        result, info = schema.enrich_known_schemas(original)
        pd.testing.assert_frame_equal(original, result[original.columns])
        self.assertTrue(info.siri_detected)
        self.assertEqual(result[schema.DERIVED_TIPO_INFORMACAO].tolist(), ["Oferta", "Guia ITBI"])
        self.assertEqual(result[schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA].tolist(),
                         [schema.FINALIDADE_CASA, schema.FINALIDADE_GLEBA])
        self.assertEqual(result["valor_oferta"].tolist(), [500000, 200000])
        self.assertEqual(result[schema.DERIVED_AREA_LOTE].tolist(), [600, 100])
        self.assertEqual(result.loc[0, schema.DERIVED_AREA_CONSTRUIDA], 120)
        self.assertEqual(result.loc[0, schema.DERIVED_AREA_PRIVATIVA], 100)
        self.assertNotIn("siat_ano", result)

    def test_guide_missing_declared_price_or_transmitted_area_has_no_fiscal_fallback(self):
        result, _ = schema.enrich_known_schemas(export_frame(
            valorGuiaTotalDeclarado=[None, None], guiaAreaTerrTransmitida=[None, 0]
        ))
        self.assertTrue(pd.isna(result.loc[1, "valor_oferta"]))
        self.assertTrue(pd.isna(result.loc[1, schema.DERIVED_AREA_LOTE]))

    def test_coordinates_are_selected_as_pairs_without_cross_source_mixing(self):
        result, _ = schema.enrich_known_schemas(export_frame(
            endLatitudeCrawler=[-30.01, -30.02], endLongitudeCrawler=[None, None],
            endLatitudePmi=[-30.04, None], endLongitudePmi=[-51.24, -51.25],
        ))
        self.assertEqual((result.loc[0, "latitude"], result.loc[0, "longitude"]), (-30.04, -51.24))
        self.assertTrue(pd.isna(result.loc[1, "latitude"]))
        self.assertTrue(pd.isna(result.loc[1, "longitude"]))
        self.assertEqual(result.loc[0, "__origem_coordenadas_exportacao"], "Pmi")

    def test_address_number_is_not_taken_from_another_street(self):
        result, _ = schema.enrich_known_schemas(export_frame())
        self.assertEqual(result.loc[0, "logradouro"], "Rua de Teste")
        self.assertTrue(pd.isna(result.loc[0, "numero"]))
        self.assertEqual(result.loc[1, "logradouro"], "Rua Sintética")
        self.assertEqual(result.loc[1, "numero"], 30)

    def test_condominium_uses_private_offer_area_and_transmitted_guide_area(self):
        result, _ = schema.enrich_known_schemas(export_frame(
            finalidadeNmeCrawlerSiri=["Terreno em Condomínio", ""],
            finalidadeNmeSiat=["Terreno em Condomínio", "Terreno em Condomínio"],
            areaTerrPrivSiat=[80, 1000],
        ))
        self.assertEqual(result[schema.DERIVED_AREA_LOTE].tolist(), [80, 100])
        missing, _ = schema.enrich_known_schemas(export_frame(
            finalidadeNmeCrawlerSiri=["Terreno em Condomínio", ""],
        ))
        self.assertTrue(pd.isna(missing.loc[0, schema.DERIVED_AREA_LOTE]))

    def test_existing_aliases_are_preserved_on_repeated_enrichment(self):
        original = export_frame()
        first, _ = schema.enrich_known_schemas(original)
        second, info = schema.enrich_known_schemas(first)
        self.assertTrue(info.siri_detected)
        pd.testing.assert_series_equal(first["valor_oferta"], second["valor_oferta"])
        pd.testing.assert_series_equal(first[schema.DERIVED_AREA_LOTE], second[schema.DERIVED_AREA_LOTE])
        self.assertFalse(second["id_anuncio"].eq("crawler:0").any())


if __name__ == "__main__":
    unittest.main()
