from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.request import urlretrieve


SOURCE_BASE_URL = (
    "https://huggingface.co/spaces/fschwartzer/Geocode/resolve/main"
)
REQUIRED_AXIS_FILES = ("Eixos.shp", "Eixos.shx", "Eixos.dbf", "Eixos.prj")
EXPECTED_SHA256 = {
    "Eixos.shp": "91d3099c49daa703fd20a347842c68b9c0f2deb7bb519696c9a45c00fa6e674e",
    "Eixos.shx": "edb0721cc96cbcfc4e98f1ec0db3e5b2a16a8f1d3d2998ddc3a32aee4eded0cc",
    "Eixos.dbf": "a76d2b0ac8be3b7db91dfb862e019ce6f15db402aa02e5289a9050bf87a26d41",
    "Eixos.prj": "8fd6f5a2d66ef6e387dacc2fa8c5eaf40f4c7487cc0779e31769f23e99bce7d3",
}


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float | None
    longitude: float | None
    method: str
    matched_street: str = ""
    similarity_score: float = 0.0
    cdlog: int | None = None
    failure_reason: str = ""


@dataclass
class StreetAxisIndex:
    reader: Any
    fields: dict[str, int]
    names: tuple[str, ...]
    name_to_cdlog: dict[str, int]
    record_indices_by_cdlog: dict[int, tuple[int, ...]]
    transformer: Any


def parse_street_and_number(address: Any) -> tuple[str, int | None]:
    """Extrai logradouro e número de endereços brasileiros usuais."""
    text = " ".join(str(address or "").strip().split())
    if not text:
        return "", None

    patterns = (
        r"^\s*(.+?)\s*,\s*(?:n(?:[º°.]|ro)?|numero)?\s*(\d{1,7})(?:\D|$)",
        r"^\s*(.+?)\s+(?:n(?:[º°.]|ro)?|numero)?\s*(\d{1,7})(?:\s*[-,]|\s*$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ,-"), int(match.group(2))
    return text.split(",", 1)[0].strip(), None


def _axis_cache_directory() -> Path:
    path = Path(tempfile.gettempdir()) / "vera_geocode_eixos_poa"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_axis_files(cache_directory: Path | None = None) -> Path:
    """Materializa os quatro arquivos mínimos do eixo viário do Space Geocode."""
    directory = cache_directory or _axis_cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_AXIS_FILES:
        destination = directory / filename
        expected_hash = EXPECTED_SHA256[filename]
        current_hash = (
            hashlib.sha256(destination.read_bytes()).hexdigest()
            if destination.is_file()
            else ""
        )
        if current_hash == expected_hash:
            continue
        urlretrieve(f"{SOURCE_BASE_URL}/{filename}", destination)
        downloaded_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if downloaded_hash != expected_hash:
            raise ValueError(
                f"Integridade inválida no arquivo geográfico {filename}."
            )
    return directory


def _field_value(record: Any, fields: dict[str, int], name: str) -> Any:
    position = fields.get(name)
    return record[position] if position is not None else None


def load_street_axis_index(
    cache_directory: Path | None = None,
) -> StreetAxisIndex:
    """Carrega e indexa o eixo viário usado pelo Space Geocode."""
    import shapefile
    from pyproj import CRS, Transformer

    directory = ensure_axis_files(cache_directory)
    reader = shapefile.Reader(
        str(directory / "Eixos.shp"),
        encoding="latin1",
    )
    fields = {
        str(field[0]).upper(): position
        for position, field in enumerate(reader.fields[1:])
    }

    name_to_cdlog: dict[str, int] = {}
    record_indices: dict[int, list[int]] = {}
    for index, record in enumerate(reader.iterRecords()):
        raw_cdlog = _field_value(record, fields, "CDLOG")
        if raw_cdlog is None:
            continue
        cdlog = int(raw_cdlog)
        record_indices.setdefault(cdlog, []).append(index)
        for field_name in ("NMIDELOG", "NMIDEABR"):
            raw_name = _field_value(record, fields, field_name)
            name = " ".join(str(raw_name or "").upper().split())
            if name:
                name_to_cdlog[name] = cdlog

    projection = CRS.from_wkt(
        (directory / "Eixos.prj").read_text(encoding="utf-8")
    )
    transformer = Transformer.from_crs(
        projection,
        "EPSG:4326",
        always_xy=True,
    )
    return StreetAxisIndex(
        reader=reader,
        fields=fields,
        names=tuple(name_to_cdlog),
        name_to_cdlog=name_to_cdlog,
        record_indices_by_cdlog={
            cdlog: tuple(indices)
            for cdlog, indices in record_indices.items()
        },
        transformer=transformer,
    )


def find_best_street_match(
    index: StreetAxisIndex,
    street_name: Any,
    minimum_score: float = 85.0,
) -> tuple[int | None, str, float]:
    from rapidfuzz import process

    name = " ".join(str(street_name or "").upper().split())
    if not name:
        return None, "", 0.0
    match = process.extractOne(name, index.names)
    if not match:
        return None, "", 0.0
    matched_name, score, _ = match
    if float(score) < float(minimum_score):
        return None, str(matched_name), float(score)
    return index.name_to_cdlog[str(matched_name)], str(matched_name), float(score)


def _number_range(
    record: Any,
    fields: dict[str, int],
    number: int,
) -> tuple[float | None, float | None]:
    names = (
        ("NRPARINI", "NRPARFIN")
        if number % 2 == 0
        else ("NRIMPINI", "NRIMPFIN")
    )
    try:
        start = float(_field_value(record, fields, names[0]))
        end = float(_field_value(record, fields, names[1]))
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(start) or not math.isfinite(end):
        return None, None
    return start, end


def _interpolate_shape(shape: Any, fraction: float) -> tuple[float, float]:
    points = shape.points
    if not points:
        raise ValueError("Segmento viário sem geometria.")
    parts = list(shape.parts) + [len(points)]
    pieces: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    total_length = 0.0
    for part_start, part_end in zip(parts[:-1], parts[1:]):
        for position in range(part_start, part_end - 1):
            first = points[position]
            second = points[position + 1]
            length = math.hypot(second[0] - first[0], second[1] - first[1])
            if length <= 0:
                continue
            pieces.append((first, second, length))
            total_length += length

    if not pieces or total_length <= 0:
        return float(points[0][0]), float(points[0][1])

    target_length = min(max(float(fraction), 0.0), 1.0) * total_length
    traversed = 0.0
    for first, second, length in pieces:
        if traversed + length >= target_length:
            local = (target_length - traversed) / length
            return (
                float(first[0] + local * (second[0] - first[0])),
                float(first[1] + local * (second[1] - first[1])),
            )
        traversed += length
    return float(pieces[-1][1][0]), float(pieces[-1][1][1])


def geocode_porto_alegre_address(
    index: StreetAxisIndex,
    street_name: Any,
    number: Any,
    minimum_score: float = 85.0,
) -> GeocodeResult:
    """Replica a correspondência e interpolação do Space Geocode."""
    try:
        numeric_number = int(float(number))
    except (TypeError, ValueError):
        return GeocodeResult(
            None,
            None,
            method="eixo_poa",
            failure_reason="Número do imóvel inválido ou vazio",
        )

    cdlog, matched_name, score = find_best_street_match(
        index,
        street_name,
        minimum_score,
    )
    if cdlog is None:
        return GeocodeResult(
            None,
            None,
            method="eixo_poa",
            matched_street=matched_name,
            similarity_score=score,
            failure_reason=(
                "Nome da rua não encontrado com similaridade aceitável"
            ),
        )

    for record_index in index.record_indices_by_cdlog.get(cdlog, ()):
        record = index.reader.record(record_index)
        start, end = _number_range(record, index.fields, numeric_number)
        if start is None or end is None:
            continue
        if not min(start, end) <= numeric_number <= max(start, end):
            continue
        fraction = 0.5 if end == start else (numeric_number - start) / (end - start)
        projected_x, projected_y = _interpolate_shape(
            index.reader.shape(record_index),
            fraction,
        )
        longitude, latitude = index.transformer.transform(
            projected_x,
            projected_y,
        )
        return GeocodeResult(
            latitude=float(latitude),
            longitude=float(longitude),
            method="eixo_poa",
            matched_street=matched_name,
            similarity_score=score,
            cdlog=cdlog,
        )

    return GeocodeResult(
        None,
        None,
        method="eixo_poa",
        matched_street=matched_name,
        similarity_score=score,
        cdlog=cdlog,
        failure_reason="Número do imóvel fora do intervalo da rua encontrada",
    )
