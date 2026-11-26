"""Exploratory global Moran statistic for the official Madrid geography."""
import json
from functools import lru_cache
from hashlib import sha256

import numpy as np
import pandas as pd
import plotly.express as px

from statistical_engine import Result, numeric_values
from territories import DATA, normalize_code, official_codes


@lru_cache(maxsize=1)
def municipal_edges():
    stored = json.loads((DATA / "vecindad.json").read_text(encoding="utf-8"))
    if stored["sha256"] != sha256((DATA / "municipios.geojson").read_bytes()).hexdigest():
        raise ValueError("La vecindad debe regenerarse para la versión actual del GeoJSON.")
    edges = tuple(tuple(edge) for edge in stored["edges"])
    if len(set(edges)) != len(edges) or any(a >= b or a not in official_codes() or b not in official_codes() for a, b in edges):
        raise ValueError("La matriz de vecindad contiene códigos inválidos.")
    return edges


def moran(values, identifiers, *, permutations=999, seed=42):
    if not (99 <= permutations <= 4999 and 0 <= seed < 2**32):
        raise ValueError("Usa entre 99 y 4.999 permutaciones y una semilla no negativa.")
    frame = pd.DataFrame({"INE": identifiers.map(lambda value: normalize_code(value, "auto")),
                          "Valor": numeric_values(values)})
    frame = frame.dropna().sort_values("INE").reset_index(drop=True)
    if frame["INE"].duplicated().any():
        raise ValueError("Filtra el periodo o la categoría hasta tener una fila por municipio.")
    codes = {code: i for i, code in enumerate(frame["INE"])}
    graph = np.zeros((len(codes), len(codes)))
    for a, b in municipal_edges():
        if a in codes and b in codes:
            graph[codes[a], codes[b]] = graph[codes[b], codes[a]] = 1
    connected = graph.any(axis=1)
    weights = graph[np.ix_(connected, connected)]
    n = int(connected.sum())
    if n < 4:
        raise ValueError("Se requieren al menos cuatro municipios con datos y algún vecino en la selección.")
    frame = frame.loc[connected].copy()
    weights /= weights.sum(axis=1, keepdims=True)
    z = frame["Valor"].to_numpy(dtype=float)
    z -= z.mean()
    deviation = z.std()
    if not np.isfinite(deviation) or deviation == 0:
        raise ValueError("El indicador debe presentar variación finita entre los municipios conectados.")
    z /= deviation
    lag = weights @ z
    value = (z @ lag) / (z @ z)
    rng = np.random.default_rng(seed)
    permuted = rng.permuted(np.broadcast_to(z, (permutations, n)), axis=1)
    simulated = ((permuted @ weights.T) * permuted).sum(axis=1) / (z @ z)
    expected = -1 / (n - 1)
    p = (1 + np.count_nonzero(abs(simulated - expected) >= abs(value - expected) - 1e-12)) / (permutations + 1)
    frame["Valor estandarizado"] = z
    frame["Vecinos ponderados"] = lag
    frame["Municipio"] = frame["INE"].map(lambda code: official_codes()[code][1])
    chart = px.scatter(frame, x="Valor estandarizado", y="Vecinos ponderados", hover_name="Municipio",
                       hover_data=["INE"], title="Diagrama de Moran")
    limits = [float(z.min()), float(z.max())]
    chart.add_scatter(x=limits, y=[punto * value for punto in limits], mode="lines", name="Pendiente I de Moran")
    chart.add_hline(y=0, line_dash="dot")
    chart.add_vline(x=0, line_dash="dot")
    islands = int((~connected).sum())
    table = pd.DataFrame([{"I de Moran": value, "I esperado": expected, "p bilateral": p, "Municipios": n,
                           "Sin vecinos": islands, "Filas sin dato o código": len(values) - len(codes),
                           "Permutaciones": permutations, "Semilla": seed}])
    return Result(table, f"I de Moran = {value:.3f}, p por permutación = {p:.4g}, {n} municipios.",
                  [("Contigüidad reina sobre el GeoJSON IGN simplificado. Los polígonos con intersección forman pares "
                   "vecinos y los pesos se estandarizan por fila después de excluir islas."),
                   ("La prueba bilateral permuta los valores sobre la red fija y compara la distancia al I esperado. "
                   "El contraste supone intercambiabilidad espacial bajo la hipótesis nula."),
                   ("Un resultado global aporta evidencia sobre dependencia espacial. La interpretación de contrastes "
                   "ordinarios y residuos de regresión debe considerar sus supuestos de independencia.")], chart)
