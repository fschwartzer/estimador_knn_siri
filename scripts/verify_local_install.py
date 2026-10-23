"""Verifica recursos previamente instalados, sem baixar ou instalar arquivos."""
from pathlib import Path
import importlib
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    for module in (
        "streamlit", "pandas", "numpy", "openpyxl", "xlrd", "plotly",
        "pyproj", "shapefile", "rapidfuzz", "reportlab", "PIL",
    ):
        importlib.import_module(module)
    from geocodificador_porto_alegre import load_street_axis_index
    index = load_street_axis_index()
    if not index.names:
        raise RuntimeError("Base geográfica sem logradouros.")
    index.reader.close()
    metadata = json.loads((ROOT / "assets/lotes_fiscais.json").read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256((ROOT / "assets/lotes_fiscais.sqlite").read_bytes()).hexdigest()
    if actual_hash != metadata["database_sha256"]:
        raise RuntimeError("Integridade inválida na base local de lotes fiscais.")
    from local_parcel_map import query_parcels
    parcels, note = query_parcels((-51.231, -30.031, -51.229, -30.029))
    if not parcels["features"]:
        raise RuntimeError(note)
    print("Instalação local validada: dependências, eixo viário e lotes fiscais.")


if __name__ == "__main__":
    main()
