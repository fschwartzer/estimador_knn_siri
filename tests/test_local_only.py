import ast
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import geocodificador_porto_alegre as geocoder

ROOT = Path(__file__).resolve().parents[1]


class LocalOnlyTests(unittest.TestCase):
    def test_missing_and_corrupt_axis_fail_without_network_or_writes(self):
        with TemporaryDirectory(dir=ROOT / "tests") as tmp, patch.object(
            socket.socket, "connect", side_effect=AssertionError("Rede proibida")
        ):
            directory = Path(tmp)
            with self.assertRaisesRegex(FileNotFoundError, "Nenhum download"):
                geocoder.ensure_axis_files(directory)
            self.assertEqual(list(directory.iterdir()), [])
            (directory / "Eixos.shp").write_bytes(b"corrompido")
            with self.assertRaisesRegex(ValueError, "Integridade"):
                geocoder.ensure_axis_files(directory)

    def test_installed_axis_and_known_address_work_without_network(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Rede proibida")):
            index = geocoder.load_street_axis_index()
            try:
                result = geocoder.geocode_porto_alegre_address(
                    index, "Avenida Borges de Medeiros", 2244
                )
                self.assertIsNotNone(result.latitude)
                self.assertIsNotNone(result.longitude)
                self.assertEqual(result.method, "eixo_poa")
            finally:
                index.reader.close()

    def geocode_namespace(self, index_loader, warnings):
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "geocode_queries")
        function.decorator_list = []
        namespace = {
            "st": SimpleNamespace(warning=warnings.append),
            "cached_street_axis_index": index_loader,
            "parse_street_and_number": geocoder.parse_street_and_number,
            "geocode_porto_alegre_address": geocoder.geocode_porto_alegre_address,
            "normalize_text": lambda text: text.casefold(),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
        return namespace["geocode_queries"]

    def test_axis_success_does_not_send_address_to_nominatim(self):
        index = geocoder.load_street_axis_index()
        remote = MagicMock()
        try:
            function = self.geocode_namespace(lambda: index, [])
            query = "Avenida Borges de Medeiros, 2244, Porto Alegre"
            with patch("geopy.geocoders.Nominatim", return_value=remote):
                result = function((query,))[query]
            self.assertEqual(result["method"], "eixo_poa")
            self.assertIsNotNone(result["latitude"])
            remote.geocode.assert_not_called()
        finally:
            index.reader.close()

    def test_axis_miss_uses_nominatim_fallback(self):
        remote = MagicMock()
        remote.geocode.return_value = SimpleNamespace(latitude=-30.03, longitude=-51.23)
        function = self.geocode_namespace(lambda: object(), [])
        query = "Rua não resolvida, 10, Porto Alegre"
        with patch("geopy.geocoders.Nominatim", return_value=remote):
            # A função extraída recebe sua dependência explicitamente no namespace.
            function.__globals__["geocode_porto_alegre_address"] = lambda *args: geocoder.GeocodeResult(
                None, None, "eixo_poa", failure_reason="Rua não encontrada"
            )
            result = function((query,))[query]
        self.assertEqual(result["method"], "nominatim")
        self.assertEqual(result["latitude"], -30.03)
        remote.geocode.assert_called_once_with(query, exactly_one=True, language="pt-BR")

    def test_missing_axis_warns_and_uses_nominatim_without_downloading_axis(self):
        warnings = []
        function = self.geocode_namespace(
            lambda: (_ for _ in ()).throw(FileNotFoundError("Base local ausente")), warnings
        )
        remote = MagicMock()
        remote.geocode.return_value = None
        with patch("geopy.geocoders.Nominatim", return_value=remote):
            result = function(("Rua inexistente, 10",))["Rua inexistente, 10"]
        self.assertIn("Base local ausente", warnings[0])
        self.assertIn("Nominatim", warnings[0])
        self.assertIsNone(result["latitude"])
        remote.geocode.assert_called_once()

    def test_map_services_restored_but_axis_has_no_download_code(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"carto-positron"', source)
        self.assertIn('"open-street-map"', source)
        self.assertIn('"white-bg"', source)
        self.assertNotIn("local_parcel_map", source)
        axis_source = (ROOT / "geocodificador_porto_alegre.py").read_text(encoding="utf-8")
        self.assertNotIn("huggingface.co", axis_source)
        self.assertNotIn("urlretrieve", axis_source)
        self.assertNotIn("urlopen", axis_source)
        config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
        self.assertIn("gatherUsageStats = false", config)


if __name__ == "__main__":
    unittest.main()
