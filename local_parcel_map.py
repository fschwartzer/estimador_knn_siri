"""Cartografia visual local. Não participa do cálculo ou da seleção do KNN."""
from __future__ import annotations

import json
from contextlib import closing
import math
from pathlib import Path
import sqlite3
import zlib

PARCEL_DATABASE = Path(__file__).resolve().parent / "assets" / "lotes_fiscais.sqlite"
MAX_PARCELS = 20000


def viewport_bounds(latitude: float, longitude: float, zoom: float,
                    width: int = 1400, height: int = 660) -> tuple[float, float, float, float]:
    """Retângulo de apresentação Web Mercator; coordenadas em graus WGS84."""
    scale = 256 * 2 ** zoom
    center_x = (longitude + 180) / 360 * scale
    lat = math.radians(max(-85.0511, min(85.0511, latitude)))
    center_y = (1 - math.asinh(math.tan(lat)) / math.pi) / 2 * scale
    def latitude_at(y):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / scale))))
    return (max(-180, (center_x - width / 2) / scale * 360 - 180),
            max(-85.0511, latitude_at(center_y + height / 2)),
            min(180, (center_x + width / 2) / scale * 360 - 180),
            min(85.0511, latitude_at(center_y - height / 2)))


def query_parcels(bounds, database: Path | None = None, limit: int = MAX_PARCELS):
    """Consulta RTree somente leitura; não trunca o tecido urbano silenciosamente."""
    if len(bounds) != 4 or not all(math.isfinite(float(x)) for x in bounds):
        raise ValueError("Retângulo cartográfico inválido.")
    west, south, east, north = map(float, bounds)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Limites cartográficos fora de WGS84 ou invertidos.")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PARCELS:
        raise ValueError("Limite de lotes inválido.")
    empty = {"type": "FeatureCollection", "features": []}
    path = database if database is not None else PARCEL_DATABASE
    if not path.is_file():
        return empty, "Base local de lotes ausente; instale assets/lotes_fiscais.sqlite."
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            rows = connection.execute(
                "SELECT p.geometry FROM bounds b JOIN parcels p ON p.id=b.id "
                "WHERE b.west<=? AND b.east>=? AND b.south<=? AND b.north>=? LIMIT ?",
                (east, west, north, south, limit + 1),
            ).fetchall()
        if len(rows) > limit:
            return empty, f"Região ampla: mais de {limit:,} lotes. Reduza a abrangência cartográfica."
        features = [{"type": "Feature", "properties": {},
                     "geometry": json.loads(zlib.decompress(row[0]))} for row in rows]
    except (sqlite3.Error, zlib.error, ValueError) as exc:
        return empty, f"Base local de lotes inválida ({type(exc).__name__}); reinstale a base."
    if not features:
        return empty, "Sem lotes fiscais na região consultada; cobertura cadastral não confirmada."
    return {"type": "FeatureCollection", "features": features}, (
        f"Lotes fiscais SMAMUS: {len(features):,} polígonos locais. "
        "Suporte visual; não comprova vínculo cadastral dos pontos."
    )


def parcel_rings(feature_collection):
    """Inclui contornos exteriores e interiores, sem preencher pátios ou vazios."""
    for feature in feature_collection["features"]:
        geometry = feature["geometry"]
        polygons = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
                    else geometry["coordinates"])
        for polygon in polygons:
            yield from polygon
