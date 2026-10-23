"""Verifica recursos previamente instalados, sem baixar ou instalar arquivos."""
from pathlib import Path
import importlib
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
    print("Instalação local validada: dependências e base geográfica íntegra.")


if __name__ == "__main__":
    main()
