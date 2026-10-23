"""Prepara uma cópia cartográfica indexada sem alterar a fonte GeoJSON."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib


def prepare(source: Path, destination: Path):
    if destination.exists():
        raise FileExistsError(f"Destino já existe: {destination}")
    raw = source.read_bytes()
    data = json.loads(raw)
    if data.get("type") != "FeatureCollection":
        raise ValueError("Fonte deve ser uma FeatureCollection GeoJSON WGS84.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with closing(sqlite3.connect(destination)) as db, db:
        db.execute("CREATE TABLE parcels(id INTEGER PRIMARY KEY, geometry BLOB NOT NULL)")
        db.execute("CREATE VIRTUAL TABLE bounds USING rtree(id,west,east,south,north)")
        for feature in data["features"]:
            geometry = feature.get("geometry")
            if not geometry or geometry["type"] not in ("Polygon", "MultiPolygon"):
                raise ValueError("Fonte contém feição sem polígono; preparação interrompida.")
            polygons = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
                        else geometry["coordinates"])
            points = [p for polygon in polygons for ring in polygon for p in ring]
            if not points or not all(-52 < p[0] < -50 and -31 < p[1] < -29 for p in points):
                raise ValueError("Coordenadas incompatíveis com longitude/latitude de Porto Alegre.")
            # Conserva integralmente as coordenadas; remove atributos não necessários ao desenho.
            total += 1
            db.execute("INSERT INTO parcels VALUES (?,?)", (total, zlib.compress(
                json.dumps(geometry, separators=(",", ":")).encode(), level=9)))
            xs, ys = zip(*[p[:2] for p in points])
            db.execute("INSERT INTO bounds VALUES (?,?,?,?,?)",
                       (total, min(xs), max(xs), min(ys), max(ys)))
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)")
        metadata = {"source_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_file": source.name, "features": total,
                    "crs": "EPSG:4326", "purpose": "visual_only"}
        db.executemany("INSERT INTO metadata VALUES (?,?)",
                       [(k, str(v)) for k, v in metadata.items()])
    metadata["database_sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
