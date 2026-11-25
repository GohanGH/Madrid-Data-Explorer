"""Regenera extractos reproducibles a partir de CSV oficiales."""
import argparse
import csv
import json
from io import StringIO
from pathlib import Path

import requests

HEALTH = "centros_sanitarios_por_tipo"
CENSUS = "censo_anual_por_edad"
HEALTH_COUNT = "centros_atencion_primaria_recuento"
ROOT = Path(__file__).resolve().parent
RULES = {
    "irpf_indicador_renta": ("Renta per cápita (EUR)", {"Medida": "Per cápita"}),
    "grado_envejecimiento_por_edad": ("Población de 65 años y más (%)", {"Edad": "65 años y más"}),
    "centros_sanitarios_por_tipo": ("Centros por 10.000 habitantes", {
        "Tipo": "Consultorios locales y centros de salud", "Medida": "Por 10.000 habitantes"}),
    HEALTH_COUNT: ("Centros de atención primaria (número)", {
        "Tipo": "Consultorios locales y centros de salud", "Medida": "Total"}),
    "padron_por_sexo": ("Población (personas)", {"Sexo": "Total"}),
    "302038": ("Paro registrado (personas)", {}),
}
KEYS = ["Código territorio", "Año", "Territorio"]


def source_filename(source):
    return f"mde-{'paro' if source == '302038' else source}.csv"


def source_bytes(sources, source, local):
    try:
        if local:
            return (local / source_filename(source)).read_bytes()
        response = requests.get(sources[source]["url"], timeout=(5, 30))
        response.raise_for_status()
        return response.content
    except OSError as exc:
        raise ValueError(f"No se pudo cargar {source}: {exc}") from exc


def census_extract(contents):
    reader = csv.DictReader(StringIO(contents), delimiter=";")
    required = {*KEYS, "Edad", "Tipo territorio", "Nacionalidad", "Sexo", "Valor"}
    if not required.issubset(reader.fieldnames or ()):
        raise ValueError(f"Esquema inesperado en {CENSUS}: {reader.fieldnames}")
    return sorted([*(row[key] for key in KEYS), row["Edad"], row["Valor"]]
                  for row in reader if row["Año"] == "2024" and row["Tipo territorio"] == "Municipios"
                  and row["Nacionalidad"] == row["Sexo"] == "Total")


def build(local, output, save_raw=None):
    if save_raw and save_raw.exists():
        raise ValueError("El destino de los originales debe ser una carpeta nueva.")
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    regional = []
    raw = {}
    extracts = {}
    for name, (metric, conditions) in RULES.items():
        years = range(2018, 2026) if name == "302038" else range(2015, 2026) if name == "padron_por_sexo" else [2024]
        source = HEALTH if name == HEALTH_COUNT else name
        if source not in raw:
            raw[source] = source_bytes(sources, source, local)
        reader = csv.DictReader(StringIO(raw[source].decode("utf-8-sig")), delimiter=";")
        required = {*KEYS, "Tipo territorio", "Valor", *conditions}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Esquema inesperado en {source}: {reader.fieldnames}")
        extracted = []
        seen = set()
        for row in reader:
            if int(row["Año"]) not in years or any(row[col] != value for col, value in conditions.items()):
                continue
            if name != HEALTH_COUNT and row["Tipo territorio"] == "Comunidad de Madrid":
                regional.append([name, row["Año"], row["Valor"]])
            if row["Tipo territorio"] != "Municipios":
                continue
            key = [row[c] for c in KEYS]
            if not key[0] or tuple(key[:2]) in seen:
                raise ValueError(f"Clave municipal anual no única en {name}: {key}")
            seen.add(tuple(key[:2]))
            value = row["Valor"]
            extracted.append([*key, "" if value == "-" else value])
        if len(extracted) != 179 * len(years):
            raise ValueError(f"Cobertura inesperada en {name}: {len(extracted)} registros.")
        extracts[name] = (metric, extracted)
    raw[CENSUS] = source_bytes(sources, CENSUS, local)
    census = census_extract(raw[CENSUS].decode("utf-8-sig"))
    if len(census) != 179 * 22:
        raise ValueError(f"Cobertura censal inesperada: {len(census)} registros.")
    if save_raw:
        save_raw.mkdir(parents=True)
        for source, contents in raw.items():
            (save_raw / source_filename(source)).write_bytes(contents)
    output.mkdir(parents=True, exist_ok=True)
    for name, (metric, extracted) in extracts.items():
        with (output / f"{name}.csv").open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target, lineterminator="\n")
            writer.writerow([*KEYS, metric])
            writer.writerows(sorted(extracted))
    with (output / f"{CENSUS}.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow([*KEYS, "Edad", "Población censada (personas)"])
        writer.writerows(census)
    with (output / "regional.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(["Fuente", "Año", "Valor"])
        writer.writerows(sorted(regional))


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    source = cli.add_mutually_exclusive_group()
    source.add_argument("--local", type=Path, help="Lee las descargas originales desde esta carpeta.")
    source.add_argument("--save-raw", type=Path, help="Guarda las descargas originales en una carpeta nueva.")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        build(args.local, args.output, args.save_raw)
    except (OSError, ValueError) as exc:
        cli.exit(1, f"{exc}\n")
