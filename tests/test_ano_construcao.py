import unittest

import numpy as np
import pandas as pd

import estimador_knn_core_v6120 as core


def make_mapping() -> core.ColumnMapping:
    return core.ColumnMapping(
        tipo_informacao="tipo",
        finalidade_oferta="finalidade",
        valor="valor",
        area_construida="area_construida",
        area_privativa="area_privativa",
        latitude="latitude",
        longitude="longitude",
        siat_area_total_lote="area_lote",
        testada="testada",
        ano_construcao="siat_ano",
    )


class ConstructionYearFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping = make_mapping()

    def test_built_property_uses_area_and_construction_year(self) -> None:
        target = {
            "area_construida": 120.0,
            "area_privativa": None,
            "siat_area_total_lote": None,
            "testada": None,
            "ano_construcao": 1995,
            "latitude": -30.03,
            "longitude": -51.23,
        }

        features, territorial = core._resolve_features(
            self.mapping,
            target,
            territorial=False,
        )

        self.assertFalse(territorial)
        self.assertEqual(
            features,
            [
                ("area_construida", "area_construida"),
                ("ano_construcao", "siat_ano"),
            ],
        )

    def test_territorial_property_does_not_use_construction_year(self) -> None:
        target = {
            "area_construida": None,
            "area_privativa": None,
            "siat_area_total_lote": 450.0,
            "testada": 12.0,
            "ano_construcao": None,
            "latitude": -30.03,
            "longitude": -51.23,
        }

        features, territorial = core._resolve_features(
            self.mapping,
            target,
            territorial=True,
        )

        self.assertTrue(territorial)
        self.assertEqual(
            features,
            [
                ("siat_area_total_lote", "area_lote"),
                ("testada", "testada"),
            ],
        )

    def test_invalid_target_year_is_rejected(self) -> None:
        for invalid_year in (
            None,
            core.MIN_CONSTRUCTION_YEAR - 1,
            core.MAX_CONSTRUCTION_YEAR + 1,
            2000.5,
        ):
            with self.subTest(invalid_year=invalid_year):
                target = {
                    "area_construida": 120.0,
                    "area_privativa": None,
                    "siat_area_total_lote": None,
                    "testada": None,
                    "ano_construcao": invalid_year,
                    "latitude": -30.03,
                    "longitude": -51.23,
                }
                with self.assertRaisesRegex(ValueError, "ano da construção"):
                    core._resolve_features(
                        self.mapping,
                        target,
                        territorial=False,
                    )

    def test_valid_year_mask_rejects_missing_future_and_fractional_values(self) -> None:
        values = pd.Series(
            [
                2000,
                "1990",
                np.nan,
                core.MIN_CONSTRUCTION_YEAR - 1,
                core.MAX_CONSTRUCTION_YEAR + 1,
                2000.5,
            ]
        )

        self.assertEqual(
            core.valid_construction_year_mask(values).tolist(),
            [True, True, False, False, False, False],
        )

    def test_construction_year_changes_physical_distance(self) -> None:
        candidates = pd.DataFrame(
            {
                "area_construida": [100.0, 100.0, 100.0],
                "siat_ano": [1990.0, 2000.0, 2010.0],
                "latitude": [-30.03, -30.03, -30.03],
                "longitude": [-51.23, -51.23, -51.23],
            }
        )
        target = {
            "area_construida": 100.0,
            "ano_construcao": 2000.0,
            "latitude": -30.03,
            "longitude": -51.23,
        }

        distances, physical, _, _ = core._distance_profile(
            candidates,
            self.mapping,
            [
                ("area_construida", "area_construida"),
                ("ano_construcao", "siat_ano"),
            ],
            target,
            similarity_weight=0.8,
        )

        self.assertEqual(int(np.argmin(distances)), 1)
        self.assertEqual(int(np.argmin(physical)), 1)
        self.assertAlmostEqual(float(distances[1]), 0.0)
        self.assertGreater(float(distances[0]), float(distances[1]))

    def test_estimate_audits_candidates_with_invalid_year(self) -> None:
        data = pd.DataFrame(
            {
                "tipo": ["guia itbi"] * 4,
                "finalidade": ["casa / residencia"] * 4,
                "valor": [300_000.0, 310_000.0, 320_000.0, 330_000.0],
                "area_construida": [100.0, 105.0, 110.0, 115.0],
                "area_privativa": [np.nan] * 4,
                "area_lote": [np.nan] * 4,
                "testada": [np.nan] * 4,
                "siat_ano": [1990.0, 2000.0, 2010.0, np.nan],
                "latitude": [-30.030, -30.031, -30.032, -30.033],
                "longitude": [-51.230, -51.231, -51.232, -51.233],
                "_valor_unitario_ajustado": [3000.0, 2950.0, 2900.0, 2850.0],
            }
        )
        preparation = core.PreparationResult(
            data=data,
            discount=0.0,
            diagnostics={"purpose": "casa / residencia"},
            excluded_data=data.iloc[0:0].copy(),
            flagged_data=data.iloc[0:0].copy(),
        )
        target = {
            "area_construida": 105.0,
            "area_privativa": None,
            "siat_area_total_lote": None,
            "testada": None,
            "ano_construcao": 2000.0,
            "latitude": -30.031,
            "longitude": -51.231,
        }

        result = core.estimate_knn(
            preparation=preparation,
            mapping=self.mapping,
            target=target,
            reference_area_column="area_construida",
            min_k=2,
            max_k=3,
            min_effective_neighbors=1.0,
            similarity_weight=0.8,
            distance_power=1.0,
            max_individual_weight=1.0,
            robust_mad_threshold=2.0,
            territorial=False,
        )

        self.assertIn("siat_ano", result.active_features)
        self.assertEqual(
            result.diagnostics["construction_year_invalid_excluded"],
            1,
        )
        self.assertEqual(
            result.diagnostics["n_candidates_after_physical_validation"],
            3,
        )
        self.assertIn(
            "validação do ano da construção",
            result.local_excluded_data["_etapa_controle"].tolist(),
        )


if __name__ == "__main__":
    unittest.main()
