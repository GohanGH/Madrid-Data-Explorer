"""Immutable table data, editable metadata and lineage within one research project."""
from datetime import datetime, timezone
from uuid import uuid4

MAX_TABLES = 30
MAX_CELLS = 4_000_000
MAX_RAW = 24 * 1024**2
KINDS = ("Original", "Transformada", "Combinada", "Derivada")


def initialize(state):
    for key, value in {"tables": {}, "undo": [], "redo_stack": [], "serial": 0,
                       "project_results": [], "project_details": {}, "active_table": None}.items():
        state.setdefault(key, value)


def visible_tables(state):
    return {key: item for key, item in state["tables"].items() if not item.get("archived")}


def active_key(state):
    available = visible_tables(state)
    candidate = state.get("active_table")
    if candidate not in available:
        candidate = next(iter(available), None)
        state["active_table"] = candidate
    return candidate


def table_kind(item):
    if item.get("kind") in KINDS:
        return item["kind"]
    if item.get("history"):
        if item["history"][-1].get("operación") == "unión":
            return "Combinada"
        if item.get("parent"):
            return "Transformada"
    return "Original"


def store_table(state, title, df, sources=(), history=(), reversible=False, *, metadata=None, kind="Original",
                parents=(), raw=None, filename=None, supersedes=None, roles=None, focus=True):
    tables = state["tables"]
    title = str(title).strip()[:200]
    if not title or not df.columns.is_unique or not len(df.columns):
        raise ValueError("La tabla necesita un nombre y columnas únicas.")
    if len(df) > 250_000 or len(df.columns) > 3600:
        raise ValueError("La tabla supera 250.000 filas o 3.600 columnas.")
    if len(tables) >= MAX_TABLES or sum(item["df"].size for item in tables.values()) + df.size > MAX_CELLS:
        raise ValueError("Se alcanzó el límite de tablas o celdas. Libera una versión sin dependencias.")
    if raw is not None and (len(raw) > 15 * 1024**2 or sum(len(item.get("raw", b"")) for item in tables.values()) + len(raw) > MAX_RAW):
        raise ValueError("El proyecto supera el límite de 24 MB para archivos originales.")
    if any(parent not in tables for parent in parents) or (supersedes is not None and supersedes not in tables):
        raise ValueError("La versión de origen ya no está disponible.")
    state["serial"] += 1
    key = state["serial"]
    item = {"title": title, "df": df.reset_index(drop=True), "sources": tuple(dict.fromkeys(sources)),
            "history": tuple(history), "metadata": metadata or {}, "kind": kind, "parents": tuple(parents),
            "snapshot": uuid4().hex, "created": datetime.now(timezone.utc).isoformat()}
    if parents:
        item["parent"] = parents[0]
        item["original"] = tables[parents[0]].get("original", parents[0])
    if raw is not None:
        item.update(raw=raw, filename=str(filename or "original").strip()[:200])
    if supersedes is not None:
        item["supersedes"] = supersedes
    if roles:
        item["roles"] = {column: role for column, role in roles.items() if column in df}
    tables[key] = item
    if reversible:
        state["undo"].append(key)
        state["redo_stack"].clear()
    if focus or active_key(state) is None:
        state["active_table"] = key
    return key


def parent_keys(item):
    return tuple(item.get("parents") or ([item["parent"]] if "parent" in item else []))


def lineage(tables, key):
    found, pending = set(), [key]
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(parent_keys(tables.get(current, {})))
    return found


def version_warnings(tables, key):
    refs = lineage(tables, key)
    updates = {item.get("supersedes") for item in tables.values() if not item.get("archived")}
    messages = []
    if refs & updates:
        messages.append("Hay una revisión posterior de un dato o de una operación en su linaje.")
    if any(ref not in tables or tables[ref].get("archived") for ref in refs):
        messages.append("Una tabla de origen está retirada de la biblioteca activa.")
    return messages


def retire_table(state, key):
    """Hide a version without changing the observations in that version."""
    state["tables"][key]["archived"] = True
    active_key(state)


def remove_unused(state, key):
    tables = state["tables"]
    if any(key in parent_keys(item) or item.get("supersedes") == key for item in tables.values()):
        raise ValueError("Otras versiones conservan una referencia a esta tabla.")
    if any(result["dataset"] == key for result in state["project_results"]):
        raise ValueError("Hay resultados guardados que utilizan esta tabla.")
    del tables[key]
    for name in ("undo", "redo_stack"):
        state[name][:] = [entry for entry in state[name] if entry != key]
    active_key(state)


def undo_table(state):
    while state["undo"]:
        key = state["undo"].pop()
        if key in state["tables"] and not state["tables"][key].get("archived"):
            retire_table(state, key)
            state["redo_stack"].append(key)
            return key
    return None


def redo_table(state):
    if not state["redo_stack"]:
        return None
    key = state["redo_stack"].pop()
    state["tables"][key]["archived"] = False
    state["undo"].append(key)
    state["active_table"] = key
    return key
