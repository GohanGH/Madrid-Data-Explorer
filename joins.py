"""Uniones tabulares verificables entre fuentes, sin modelos de IA."""
import pandas as pd


def join_preview(left: pd.DataFrame, right: pd.DataFrame, left_key: list[str], right_key: list[str],
                 how: str, max_rows: int = 250_000) -> tuple[pd.DataFrame, dict]:
    if not left_key or len(left_key) != len(right_key) or any(x not in left for x in left_key) or any(x not in right for x in right_key):
        raise ValueError("La columna de unión no existe.")
    if how not in {"inner", "left", "right", "outer"}:
        raise ValueError("Tipo de unión no permitido.")
    l = left.copy()
    r = right.copy()
    # Normalización de claves: preserva ceros iniciales y no convierte identificadores a enteros.
    def keys(df, cols, prefix):
        parts = [df[c].astype("string").str.strip().str.casefold() for c in cols]
        missing = pd.concat([p.isna() | p.eq("") for p in parts], axis=1).any(axis=1)
        tuples = pd.Series(list(zip(*[p.fillna("").tolist() for p in parts])), index=df.index, dtype="object")
        for position in range(len(tuples)):
            if bool(missing.iloc[position]):
                tuples.iloc[position] = (prefix, position)
        return tuples, int(missing.sum())

    l["__join_key"], missing_l = keys(l, left_key, "LEFT-MISSING")
    r["__join_key"], missing_r = keys(r, right_key, "RIGHT-MISSING")
    ldupes = int(l["__join_key"].duplicated().sum())
    rdupes = int(r["__join_key"].duplicated().sum())
    # Estimate output size including unmatched keys before allocating an explosive many-to-many join.
    lc = l["__join_key"].value_counts()
    rc = r["__join_key"].value_counts()
    overlap = lc.index.intersection(rc.index)
    matched = sum(int(lc[k]) * int(rc[k]) for k in overlap)
    left_unmatched = len(l) - int(l["__join_key"].isin(rc.index).sum())
    right_unmatched = len(r) - int(r["__join_key"].isin(lc.index).sum())
    estimate = matched + (left_unmatched if how in ("left", "outer") else 0) + (
        right_unmatched if how in ("right", "outer") else 0)
    if estimate > max_rows:
        raise ValueError(f"La unión produciría aproximadamente {estimate:,} filas; límite {max_rows:,}. "
                         "Revisa duplicados o agrega primero por municipio/año.")
    result = pd.merge(l, r, on="__join_key", how=how, suffixes=("_A", "_B"),
                      indicator=True, validate="many_to_many")
    matched_rows = int(result["_merge"].eq("both").sum())
    counts = result["_merge"].value_counts().to_dict()
    result = result.drop(columns=["__join_key"])
    info = {"filas": len(result), "filas_coincidentes": matched_rows,
            "solo_izquierda": int(counts.get("left_only", 0)),
            "solo_derecha": int(counts.get("right_only", 0)),
            "duplicados_clave_A": ldupes, "duplicados_clave_B": rdupes,
            "claves_nulas_A": missing_l,
            "claves_nulas_B": missing_r}
    return result, info
