import ast
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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

    def test_geocoding_failures_are_explicit_and_never_call_online_service(self):
        # Extrai a função sem executar a interface e seu carregamento de planilhas.
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "geocode_queries")
        function.decorator_list = []
        errors = []
        namespace = {
            "st": SimpleNamespace(error=errors.append),
            "cached_street_axis_index": lambda: (_ for _ in ()).throw(
                FileNotFoundError("Base local ausente")
            ),
            "parse_street_and_number": geocoder.parse_street_and_number,
            "normalize_text": lambda text: text.casefold(),
        }
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Rede proibida")):
            exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
            result = namespace["geocode_queries"](("Rua inexistente, 10",))
        self.assertEqual(errors, ["Base local ausente"])
        self.assertIsNone(result["Rua inexistente, 10"]["latitude"])
        self.assertEqual(result["Rua inexistente, 10"]["failure_reason"], "Base local ausente")

    def test_interactive_map_and_telemetry_are_local(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('"open-street-map"', source)
        self.assertNotIn('"carto-positron"', source)
        self.assertIn('"white-bg"', source)
        config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
        self.assertIn("gatherUsageStats = false", config)


if __name__ == "__main__":
    unittest.main()
