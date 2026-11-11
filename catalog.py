"""Acceso de solo lectura al catálogo CKAN de la Comunidad de Madrid."""
from __future__ import annotations

from urllib.parse import urlparse
import io
import json

import pandas as pd
import requests

API_ROOT = "https://datos.comunidad.madrid/api/3/action"
MAX_BYTES = 15 * 1024 * 1024
USER_AGENT = "MadridDataExplorer/0.1 (academic open-data prototype)"


def search_catalog(query: str, rows: int = 25) -> tuple[int, list[dict]]:
    response = requests.get(
        f"{API_ROOT}/package_search",
        params={"q": query.strip(), "rows": min(rows, 100)},
        headers={"User-Agent": USER_AGENT}, timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError("La API del catálogo devolvió un error.")
    result = payload["result"]
    return result["count"], result["results"]


def compatible_resources(dataset: dict) -> list[dict]:
    return [r for r in dataset.get("resources", [])
            if str(r.get("format", "")).upper() in {"CSV", "JSON", "XLSX", "XLS"}
            and str(r.get("url", "")).startswith("https://")]


def download_table(resource: dict) -> pd.DataFrame:
    url = str(resource.get("url", ""))
    parsed = urlparse(url)
    # Avoid downloading arbitrary internal addresses from catalog metadata.
    if parsed.scheme != "https" or not parsed.hostname or not (
        parsed.hostname == "comunidad.madrid"
        or parsed.hostname.endswith(".comunidad.madrid")
        or parsed.hostname == "madrid.org"
        or parsed.hostname.endswith(".madrid.org")
    ):
        raise ValueError("El recurso está alojado fuera de los dominios oficiales permitidos.")

    with requests.get(url, headers={"User-Agent": USER_AGENT},
                      timeout=45, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError("El fichero supera 15 MB. Elige otro recurso.")
    raw = bytes(data)
    fmt = str(resource.get("format", "")).upper()
    if fmt == "CSV":
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding=encoding,
                                   on_bad_lines="skip")
            except (UnicodeError, pd.errors.ParserError, ValueError):
                continue
        raise ValueError("No se pudo interpretar el CSV.")
    if fmt in {"XLS", "XLSX"}:
        return pd.read_excel(io.BytesIO(raw))
    if fmt == "JSON":
        payload = json.loads(raw)
        if isinstance(payload, dict):
            for key in ("data", "results", "result", "records", "features"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ValueError("El JSON no contiene una lista de registros tabulares.")
        return pd.json_normalize(payload)
    raise ValueError("Formato no soportado.")


def describe_table(df: pd.DataFrame) -> dict:
    return {
        "filas": len(df), "columnas": len(df.columns),
        "variables": [{"nombre": str(c), "tipo": str(df[c].dtype),
                       "faltantes": int(df[c].isna().sum())} for c in df.columns],
    }
