"""Portable, bounded project archives. Tables use Parquet and metadata uses JSON."""
import json
import math
import re
from datetime import date, datetime, timezone
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

import numpy as np
import pandas as pd
import plotly.io as pio
import pyarrow as pa
import pyarrow.parquet as pq

from workspace_state import MAX_RAW, MAX_TABLES

VERSION = 2
MAX_FILE = 15 * 1024**2
MAX_EXPANDED = 96 * 1024**2
MAX_MANIFEST = 24 * 1024**2
MAX_RESULTS = 48
TABLE_FIELDS = ("title", "sources", "history", "metadata", "roles", "original", "parent",
                "kind", "parents", "archived", "snapshot", "created", "filename", "supersedes")
RESULT_FIELDS = ("id", "kind", "title", "annotation", "interpretation", "created", "snapshot")
RESULT_KINDS = ("Análisis", "Gráfico", "Mapa", "Tabla")
FILE_PATTERN = re.compile(r"(?:(?:tables|results)/[1-9]\d{0,8}\.parquet|originals/[1-9]\d{0,8}\.blob)")
CONFIG_KEYS = {"question", "question_id", "question_live", "open_demo", "mde_selected_codes",
               "analysis_tool", "analysis_table", "analysis_mode", "analysis_operation", "studio_dataset",
               "studio_view", "workspace_table", "join_left", "join_method", "ai_plan",
               "active_table", "redo_stack", "data_section", "prep_section", "visual_section", "project_panel"}
CONFIG_PREFIXES = ("saved_", "studio_viewport_", "studio_filter_", "studio_values_", "analysis_year_", "auto_metric_",
                   "filter_", "values_", "method_", "primary_", "second_", "group_", "design_",
                   "predictors_", "exposure_", "positive_", "time_", "spatial_", "change_",
                   "keys_a_", "keys_b_", "join_right_", "x_", "y_", "cfg_")


def project_key(key):
    return (key in CONFIG_KEYS or key.startswith(CONFIG_PREFIXES)
            or re.fullmatch(r"family_\d+|geo_(?:code|period|first|second|metrics|system)_\d+"
                            r"|demo_\d+_(?:years|towns|rank|direction|map|mapyear|x|y|methods|figure)", key) is not None)


def _valid_config(key, value):
    if not project_key(key) or len(key) > 1200:
        return False
    if key in {"question", "open_demo"} or key.startswith("family_"):
        return value is None or isinstance(value, str)
    if key == "redo_stack":
        return isinstance(value, list) and len(value) <= MAX_TABLES and all(type(i) is int for i in value)
    if key.startswith("cfg_"):
        return (all(item is None or isinstance(item, (bool, str, int, float, pd.Timestamp)) for item in value)
                if isinstance(value, list) else value is None or isinstance(value, (bool, str, int, float, pd.Timestamp)))
    if key in {"active_table", "question_id", "analysis_table", "studio_dataset", "workspace_table", "join_left"} or key.startswith("join_right_"):
        return value is None or (type(value) is int and 0 <= value < 10**9)
    if key == "question_live" or key.startswith("design_"):
        return type(value) is bool
    if key == "ai_plan":
        return (isinstance(value, list) and len(value) == 3 and type(value[0]) is int
                and isinstance(value[1], str) and isinstance(value[2], dict))
    if key.startswith("studio_viewport_"):
        return (isinstance(value, list) and len(value) == 2 and isinstance(value[0], list) and len(value[0]) == 2
                and all(type(coord) in {int, float} and math.isfinite(coord) for coord in value[0])
                and type(value[1]) is int and 0 <= value[1] <= 25)
    if key.startswith("spatial_seed_"):
        return type(value) is int and 0 <= value < 2**32
    if key.startswith("time_window_"):
        return type(value) is int and 2 <= value <= 30

    def scalar(item):
        return item is None or isinstance(item, (bool, str, int, float, pd.Timestamp))
    if (key.startswith(("studio_values_", "values_", "predictors_", "geo_metrics_", "keys_a_", "keys_b_"))
            or key == "mde_selected_codes" or re.fullmatch(r"demo_\d+_(?:years|towns|methods)", key)):
        return isinstance(value, list) and len(value) <= 500 and all(scalar(item) for item in value)
    return scalar(value)


def _json_default(value):
    if isinstance(value, np.generic):
        value = value.item()
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (date, datetime)):
        return {"$mde_timestamp": value.isoformat()}
    if isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Tipo de metadato incompatible: {type(value).__name__}.")


def _object_hook(value):
    if set(value) == {"$mde_timestamp"}:
        return pd.Timestamp(value["$mde_timestamp"])
    return value


def _write_table(archive, path, frame):
    working = frame.reset_index(drop=True).copy(deep=False)
    encoded = []
    for column in working.select_dtypes("object"):
        try:
            inferred = pa.array(working[column], from_pandas=True)
            if not (pa.types.is_nested(inferred.type) or pa.types.is_binary(inferred.type)):
                continue
        except (pa.ArrowException, TypeError, ValueError):
            pass
        working[column] = working[column].map(lambda value: json.dumps(value, default=_json_default)).astype("string")
        encoded.append(column)
    buffer = BytesIO()
    pq.write_table(pa.Table.from_pandas(working, preserve_index=False), buffer, compression="snappy")
    archive.writestr(path, buffer.getvalue())
    return {"path": path, "encoded": encoded}


def _read_table(archive, spec, namespace, seen, budget):
    if not isinstance(spec, dict):
        raise TypeError("Descriptor de tabla inválido.")
    path, encoded = spec.get("path"), spec.get("encoded")
    if (not isinstance(path, str) or not path.startswith(namespace + "/") or not FILE_PATTERN.fullmatch(path)
            or path in seen or path not in archive.namelist() or not isinstance(encoded, list)
            or not all(isinstance(col, str) for col in encoded)):
        raise ValueError("Archivo de tabla inválido o duplicado.")
    seen.add(path)
    file = pq.ParquetFile(pa.BufferReader(archive.read(path)), thrift_string_size_limit=MAX_MANIFEST,
                          thrift_container_size_limit=100_000)
    metadata, schema = file.metadata, file.schema_arrow
    names = schema.names
    cells = metadata.num_rows * metadata.num_columns
    size = sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
    if (metadata.num_rows > 250_000 or len(names) > 3600 or len(set(names)) != len(names)
            or not set(encoded) <= set(names) or cells > budget[0] or size > budget[1]
            or any(pa.types.is_nested(field.type) or isinstance(field.type, pa.BaseExtensionType) for field in schema)):
        raise ValueError("La tabla supera los límites o contiene tipos incompatibles.")
    budget[0] -= cells
    budget[1] -= size
    frame = file.read().to_pandas()
    if list(frame) != names or len(frame) != metadata.num_rows:
        raise ValueError("El esquema y los metadatos de la tabla son incompatibles.")
    for column in encoded:
        frame[column] = frame[column].map(lambda value: json.loads(value, object_hook=_object_hook)).astype(object)
    return frame


def save_project(tables, undo, config, results, details):
    output = BytesIO()
    now = datetime.now(timezone.utc).isoformat()
    manifest = {"version": VERSION, "project": {**details, "created": details.get("created") or now, "modified": now},
                "tables": {}, "undo": [i for i in undo if i in tables],
                "config": {k: v for k, v in config.items() if project_key(k)}, "results": []}
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for key, item in tables.items():
            entry = {field: item[field] for field in TABLE_FIELDS if field in item}
            entry["data"] = _write_table(archive, f"tables/{key}.parquet", item["df"])
            if "raw" in item:
                raw_path = f"originals/{key}.blob"
                archive.writestr(raw_path, item["raw"])
                entry["original_bytes"] = raw_path
            manifest["tables"][str(key)] = entry
        chosen = [entry for entry in results if entry["dataset"] in tables]
        if len(chosen) > MAX_RESULTS:
            raise ValueError(f"El proyecto admite {MAX_RESULTS} resultados guardados.")
        for i, entry in enumerate(chosen, 1):
            data = _write_table(archive, f"results/{i}.parquet", entry["table"])
            figures = [json.loads(pio.to_json(fig)) for fig in entry["figures"]]
            manifest["results"].append({key: entry[key] for key in ("dataset", "params", "summary", "notes")}
                                       | {key: entry[key] for key in RESULT_FIELDS if key in entry}
                                       | {"data": data, "figures": figures})
        raw = json.dumps(manifest, ensure_ascii=False, default=_json_default).encode("utf-8")
        if len(raw) > MAX_MANIFEST or sum(info.file_size for info in archive.infolist()) + len(raw) > MAX_EXPANDED:
            raise ValueError("El proyecto supera el límite de tamaño. Reduce las tablas o figuras guardadas.")
        archive.writestr("manifest.json", raw)
    if output.tell() > MAX_FILE:
        raise ValueError("El proyecto supera el máximo de 15 MB comprimidos.")
    return output.getvalue()


def _text_fields(value, fields, limit):
    return isinstance(value, dict) and all(isinstance(value.get(key), str) and len(value[key]) <= limit for key in fields)


def load_project(raw):
    if not raw or len(raw) > MAX_FILE:
        raise ValueError("El proyecto debe ser un ZIP de hasta 15 MB.")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            if (len(names) > 1 + 2 * MAX_TABLES + MAX_RESULTS or len(set(names)) != len(names) or "manifest.json" not in names
                    or archive.getinfo("manifest.json").file_size > MAX_MANIFEST
                    or sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED
                    or any(name != "manifest.json" and not FILE_PATTERN.fullmatch(name) for name in names)
                    or any(info.flag_bits & 1 for info in archive.infolist())):
                raise ValueError("Estructura o tamaño del proyecto inválido.")
            manifest = json.loads(archive.read("manifest.json"), object_hook=_object_hook)
            if not isinstance(manifest, dict) or type(manifest.get("version")) is not int or manifest["version"] not in {1, VERSION}:
                raise ValueError("Versión de proyecto incompatible.")
            details, entries, undo, config, results = (manifest.get(key) for key in
                                                       ("project", "tables", "undo", "config", "results"))
            if (not _text_fields(details, ("name", "question", "description", "created", "modified"), 3000)
                    or not isinstance(entries, dict) or len(entries) > MAX_TABLES
                    or not isinstance(undo, list) or not all(type(i) is int for i in undo)
                    or not isinstance(config, dict) or not all(_valid_config(k, v) for k, v in config.items())
                    or not isinstance(results, list) or len(results) > MAX_RESULTS):
                raise ValueError("El manifiesto carece de campos válidos.")
            drafts = details.get("reports", [])
            if (not isinstance(drafts, list) or len(drafts) > 12
                    or any(not _text_fields(draft, ("id", "title"), 200)
                           or not _text_fields(draft, ("introduction", "objectives", "methodology",
                                                      "discussion", "limitations", "conclusions", "sources"), 6000)
                           or not isinstance(draft.get("entries"), list) or len(draft["entries"]) > MAX_RESULTS
                           or any(not isinstance(entry, str) or len(entry) > 200 for entry in draft["entries"])
                           for draft in drafts)):
                raise ValueError("Los borradores de informe no son válidos.")
            seen, budget, tables = {"manifest.json"}, [4_000_000, MAX_EXPANDED], {}
            raw_budget = MAX_RAW
            for key, item in entries.items():
                if (not re.fullmatch(r"[1-9]\d{0,8}", key) or not _text_fields(item, ["title"], 2000)
                        or not isinstance(item.get("sources"), list) or not all(isinstance(s, str) for s in item["sources"])
                        or not isinstance(item.get("history"), list) or not all(isinstance(s, dict) for s in item["history"])
                        or not isinstance(item.get("metadata", {}), dict) or not isinstance(item.get("roles", {}), dict)
                        or not all(isinstance(role, str) for role in item.get("roles", {}).values())
                        or any(type(item[field]) is not int for field in ("original", "parent", "supersedes") if field in item)
                        or ("parents" in item and (not isinstance(item["parents"], list)
                            or any(type(i) is not int for i in item["parents"])))
                        or any(not isinstance(item[field], str) for field in ("filename", "created", "snapshot", "kind") if field in item)
                        or ("archived" in item and type(item["archived"]) is not bool)):
                    raise ValueError("Metadatos de tabla inválidos.")
                frame = _read_table(archive, item["data"], "tables", seen, budget)
                clean = {field: item[field] for field in TABLE_FIELDS if field in item}
                clean.update(df=frame, sources=tuple(item["sources"]), history=tuple(item["history"]))
                raw_path = item.get("original_bytes")
                if raw_path is not None:
                    if raw_path != f"originals/{key}.blob" or raw_path in seen or raw_path not in names:
                        raise ValueError("El archivo original de la tabla es inválido.")
                    size = archive.getinfo(raw_path).file_size
                    if size > MAX_FILE or size > raw_budget:
                        raise ValueError("Los archivos originales superan el límite del proyecto.")
                    raw_budget -= size
                    clean["raw"] = archive.read(raw_path)
                    seen.add(raw_path)
                tables[int(key)] = clean
            if not set(undo) <= tables.keys() or len(set(undo)) != len(undo):
                raise ValueError("El historial reversible contiene referencias inválidas.")
            if "redo_stack" in config:
                config["redo_stack"] = [i for i in config["redo_stack"] if i in tables and tables[i].get("archived")]
            for key, item in tables.items():
                if any(parent >= key or parent not in tables for parent in item.get("parents", [])):
                    raise ValueError("El linaje contiene referencias inválidas.")
            budget[0] = 4_000_000
            ids = set()
            for entry in results:
                if (not _text_fields(entry, ["summary"], 10_000) or type(entry.get("dataset")) is not int
                        or entry["dataset"] not in tables or not isinstance(entry.get("params"), dict)
                        or not isinstance(entry.get("notes"), list) or not all(isinstance(note, str) for note in entry["notes"])
                        or not isinstance(entry.get("figures"), list) or len(entry["figures"]) > 8):
                    raise ValueError("Resultados guardados inválidos.")
                if any(entry[field] is not None and not isinstance(entry[field], str)
                       for field in RESULT_FIELDS if field in entry):
                    raise ValueError("Los nombres, las anotaciones o las fechas del resultado no son válidos.")
                entry.setdefault("id", uuid4().hex)
                if not entry["id"] or len(entry["id"]) > 200 or entry["id"] in ids:
                    raise ValueError("El proyecto contiene resultados duplicados o sin identificador.")
                ids.add(entry["id"])
                entry.setdefault("kind", "Análisis")
                entry.setdefault("title", str(entry["params"].get("análisis") or "Resultado"))
                entry.setdefault("annotation", "")
                entry.setdefault("interpretation", "")
                entry.setdefault("created", None)
                entry.setdefault("snapshot", tables[entry["dataset"]].get("snapshot"))
                entry["table"] = _read_table(archive, entry.pop("data"), "results", seen, budget)
                entry["figures"] = [pio.from_json(json.dumps(fig)) for fig in entry["figures"]]
            if seen != set(names):
                raise ValueError("El proyecto contiene archivos sin referencia.")
    except (BadZipFile, KeyError, TypeError, OverflowError, RuntimeError, RecursionError, pa.ArrowException) as exc:
        raise ValueError("No se pudo leer la estructura del proyecto.") from exc
    return tables, undo, config, results, details


def remember_result(state, dataset, params, table, summary, notes, figures, *, kind="Análisis", title=None, entry_id=None):
    entries = state.setdefault("project_results", [])
    updated = next((result for result in entries if result.get("id") == entry_id), None) if entry_id else None
    if len(entries) >= MAX_RESULTS and updated is None:
        raise ValueError(f"El cuaderno admite {MAX_RESULTS} resultados. Retira alguno para guardar otro.")
    item = state.get("tables", {}).get(dataset, {})
    record = {"id": entry_id or uuid4().hex, "dataset": dataset, "params": params, "table": table,
              "summary": summary, "notes": notes, "figures": figures, "kind": kind,
              "title": (title or params.get("análisis") or "Resultado")[:200],
              "snapshot": item.get("snapshot"), "created": datetime.now(timezone.utc).isoformat(),
              "annotation": "", "interpretation": ""}
    if updated is None:
        entries.append(record)
    else:
        record.update(annotation=updated.get("annotation", ""), interpretation=updated.get("interpretation", ""))
        updated.update(record)
    return record
