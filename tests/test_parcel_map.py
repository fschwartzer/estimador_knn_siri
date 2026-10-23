from pathlib import Path
import json
import ast
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from local_parcel_map import parcel_rings, query_parcels, viewport_bounds
from scripts.prepare_parcel_map import prepare

ROOT = Path(__file__).resolve().parents[1]


class ParcelMapTests(unittest.TestCase):
    def test_default_query_keeps_urban_context_above_twenty_thousand_parcels(self):
        # Recorte real que anteriormente descartava toda a camada ao superar 20 mil lotes.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Rede proibida")):
            parcels, note = query_parcels((-51.26, -30.09, -51.12, -29.99))
        self.assertGreater(len(parcels["features"]), 20000)
        self.assertNotIn("Região ampla", note)

    def test_interactive_map_embeds_local_geojson_below_the_points(self):
        import numpy as np
        import pandas as pd
        import plotly.graph_objects as go
        names = {"coordinate_to_numeric", "render_comparables_map", "calculate_map_zoom",
                 "build_map_data", "first_named_series", "money_br", "number_br"}
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        st = MagicMock()
        st.radio.return_value = "Lotes fiscais locais"
        st.select_slider.return_value = 0
        namespace = {"np": np, "pd": pd, "go": go, "st": st, "query_parcels": query_parcels}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
        neighbors = pd.DataFrame({"lat": [-30.0301, -30.0299], "lon": [-51.2301, -51.2299],
                                  "_peso_knn": [0.6, 0.4]})
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Rede proibida")):
            namespace["render_comparables_map"](neighbors, "lat", "lon", -30.03, -51.23)
        figure = st.plotly_chart.call_args.args[0]
        self.assertEqual(figure.layout.map.style, "white-bg")
        layer = figure.layout.map.layers[0]
        self.assertEqual(layer.below, "traces")
        self.assertEqual(layer.sourcetype, "geojson")
        self.assertEqual(layer.type, "fill")
        self.assertEqual(layer.opacity, 1)
        self.assertTrue(layer.source["features"])
        self.assertGreaterEqual(len(figure.data), 3)

    def test_bbox_selection_preserves_polygons_holes_and_coordinates(self):
        ring = [[-51.23, -30.03], [-51.229, -30.03], [-51.229, -30.029], [-51.23, -30.03]]
        hole = [[-51.2298, -30.0298], [-51.2296, -30.0298], [-51.2298, -30.0296], [-51.2298, -30.0298]]
        shapes = [{"type": "Polygon", "coordinates": [ring, hole]},
                  {"type": "MultiPolygon", "coordinates": [[[[-51.4, -30.2], [-51.39, -30.2],
                                                              [-51.39, -30.19], [-51.4, -30.2]]]]}]
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as tmp:
            source, db = Path(tmp) / "source.geojson", Path(tmp) / "lotes.sqlite"
            source.write_text(json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"not_for_display": "private"}, "geometry": g}
                for g in shapes]}), encoding="utf-8")
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Rede proibida")):
                prepare(source, db)
                selected, note = query_parcels((-51.231, -30.031, -51.228, -30.028), db)
                self.assertEqual(len(selected["features"]), 1)
                self.assertEqual(selected["features"][0]["geometry"], shapes[0])
                self.assertEqual(selected["features"][0]["properties"], {})
                self.assertEqual(list(parcel_rings(selected)), [ring, hole])
                all_parcels, _ = query_parcels((-51.5, -30.3, -51.1, -30.0), db)
                self.assertEqual(len(list(parcel_rings(all_parcels))), 3)
                too_broad, message = query_parcels((-51.5, -30.3, -51.1, -30.0), db, limit=1)
                self.assertEqual(too_broad["features"], [])
                self.assertIn("Região ampla", message)
                empty, message = query_parcels((-50.1, -30.1, -50.0, -30.0), db)
                self.assertEqual(empty["features"], [])
                self.assertIn("Sem lotes", message)

    def test_missing_or_invalid_database_has_explicit_notice(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as tmp:
            path = Path(tmp) / "missing.sqlite"
            _, note = query_parcels((-51.24, -30.04, -51.22, -30.02), path)
            self.assertIn("ausente", note)
            self.assertFalse(path.exists())
            path.write_bytes(b"invalid database")
            _, note = query_parcels((-51.24, -30.04, -51.22, -30.02), path)
            self.assertIn("inválida", note)

    def test_invalid_bounds_rejected(self):
        for bounds in [(1, 2, 0, 3), (0, 0, float("nan"), 1), (-181, 0, 1, 1)]:
            with self.assertRaises(ValueError):
                query_parcels(bounds)

    def test_viewport_bounds_contain_center_and_shrink_with_zoom(self):
        wide = viewport_bounds(-30.03, -51.23, 14)
        close = viewport_bounds(-30.03, -51.23, 15)
        self.assertLess(close[0], -51.23)
        self.assertGreater(close[2], -51.23)
        self.assertLess(close[1], -30.03)
        self.assertGreater(close[3], -30.03)
        self.assertAlmostEqual(wide[2] - wide[0], 2 * (close[2] - close[0]))


if __name__ == "__main__":
    unittest.main()
