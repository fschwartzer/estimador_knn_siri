"""Regressões de perda de comparáveis residenciais caros e anúncios errados."""
import unittest

import numpy as np
import pandas as pd

import estimador_knn_core_v6120 as core


class UpperTailProtectionTests(unittest.TestCase):
    def prepare(self, purpose="APARTAMENTO", extra=None, n=20):
        rows = [{"type": "Guia ITBI", "purpose": purpose, "price": vu * 100,
                 "area": 100.0, "year": 2010} for vu in np.linspace(4900, 5100, n)]
        rows += extra or []
        d = pd.DataFrame(rows)
        m = core.ColumnMapping("type", "purpose", "price", None, "area", None, None, None, None, "year")
        return core.prepare_data(d, m, purpose, "Valor total", "area"), m

    def row(self, vu, typ="Guia ITBI", purpose="APARTAMENTO", area=100):
        return {"type": typ, "purpose": purpose, "price": vu * area, "area": area, "year": 2026}

    def test_residential_high_values_survive_with_audit_alerts(self):
        for purpose in ("APARTAMENTO", "COBERTURA", "CASA / RESIDÊNCIA"):
            with self.subTest(purpose=purpose):
                p, _ = self.prepare(purpose, [self.row(20000, purpose=purpose), self.row(30000, purpose=purpose)])
                self.assertEqual(len(p.data), 22)
                self.assertEqual(p.diagnostics["prefilter_statistical_excluded"], 0)
                self.assertEqual(p.diagnostics["prefilter_upper_preserved_count"], 2)
                self.assertEqual(set(p.flagged_data["_valor_unitario_original"]), {20000, 30000})

    def test_extreme_offers_and_guides_above_both_bounds_are_still_removed(self):
        p, _ = self.prepare(extra=[self.row(30000), self.row(30000.01), self.row(10_000_000, "Oferta")])
        self.assertIn(30000, p.data["_valor_unitario_original"].values)
        self.assertEqual(set(p.excluded_data["_valor_unitario_original"]), {30000.01, 10_000_000})

    def test_protection_is_not_a_market_ceiling(self):
        rows = [self.row(vu) for vu in np.linspace(40000, 50000, 20)]
        p, _ = self.prepare(extra=rows, n=0)
        self.assertEqual(len(p.data), 20)
        self.assertGreater(p.diagnostics["prefilter_effective_upper_vu"], 50000)

    def test_lower_statistical_and_invalid_area_controls_remain(self):
        bad = self.row(30000)
        bad["area"] = 0
        p, _ = self.prepare(extra=[self.row(2000), bad])
        self.assertEqual(len(p.data), 20)
        self.assertEqual(len(p.excluded_data), 2)
        self.assertTrue(p.excluded_data["_motivo_exclusao"].str.contains("Área de referência").any())

    def test_small_itbi_sample_flags_instead_of_excluding(self):
        p, _ = self.prepare(extra=[self.row(40000)], n=8)
        self.assertEqual(len(p.data), 9)
        self.assertEqual(len(p.excluded_data), 0)
        self.assertEqual(len(p.flagged_data), 1)

    def test_final_calculation_preserves_30000_and_limits_erroneous_extremes(self):
        values = np.array([4900., 5000., 5100., 30000., 1_000_000.])
        weights = np.full(5, .2)
        _, adjusted, diag = core._robust_weighted_mean(values, weights, 1.25, upper_tail_protection=30000)
        np.testing.assert_allclose(adjusted[:4], values[:4])
        self.assertEqual(adjusted[-1], 30000)
        self.assertEqual(diag["robust_upper_tail_protection_vu"], 30000)

    def test_estimator_applies_protection_without_new_required_arguments(self):
        p, m = self.prepare(extra=[self.row(30000)])
        result = core.estimate_knn(p, m, {"area_privativa":100}, "area", min_k=21, max_k=21,
            min_effective_neighbors=2, max_individual_weight=.3)
        high = result.neighbors.loc[result.neighbors["_valor_unitario_ajustado"].eq(30000)]
        self.assertEqual(len(high), 1)
        self.assertEqual(float(high.iloc[0]["_valor_unitario_robusto"]), 30000)
        self.assertLessEqual(result.neighbors["_peso_knn"].max(), .3)

    def test_other_purposes_keep_existing_robust_treatment(self):
        p, _ = self.prepare("SALA COMERCIAL", [self.row(30000, purpose="SALA COMERCIAL")])
        self.assertEqual(p.diagnostics["prefilter_upper_tail_protection_vu"], 0)
        self.assertEqual(len(p.excluded_data), 1)


if __name__ == "__main__":
    unittest.main()
