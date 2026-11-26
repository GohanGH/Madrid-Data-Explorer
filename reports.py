"""Self-contained, escaped HTML exports for reproducible analysis."""
import json
from html import escape


def html_report(title, summary, table, metadata, figures=(), notes=(), sections=()):
    content = "".join(f"<li>{escape(str(note))}</li>" for note in notes)
    charts = "".join(fig.to_html(full_html=False, include_plotlyjs=index == 0)
                     for index, fig in enumerate(figures))
    method = escape(json.dumps(metadata, ensure_ascii=False, indent=2, default=str))
    table_html = table.to_html(index=False, escape=True)
    details = "".join(f'<section><h2>{escape(label)}</h2><div class="table">'
                      f'{data.to_html(index=False, escape=True)}</div></section>' for label, data in sections)
    return f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>body{{font:16px system-ui;background:#0D1117;color:#F0F3F6;margin:auto;max-width:76rem;padding:1rem}}
table{{border-collapse:collapse}}th,td{{border:1px solid #303A46;padding:.35rem}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.table{{overflow:auto}}
@media print{{body{{background:#fff;color:#000}}thead{{display:table-header-group}}
tr{{break-inside:avoid}}.plotly-graph-div{{break-inside:avoid}}}}</style>
<h1>{escape(title)}</h1><p>{escape(summary)}</p><ul>{content}</ul>
{charts}<div class="table">{table_html}</div>{details}<h2>Procedencia y parámetros</h2><pre>{method}</pre></html>"""


def notebook_report(draft, project, entries, tables):
    """Reproduce the selected notebook entries in one printable offline HTML document."""
    from workspace_state import version_warnings

    def paragraph(value):
        return escape(str(value)).replace("\n", "<br>")

    def text_block(label, field):
        return f"<section><h2>{label}</h2><p>{paragraph(draft[field])}</p></section>" if draft.get(field) else ""

    title = draft.get("title") or project.get("name") or "Informe de investigación"
    introduction = "".join(text_block(label, field) for label, field in (
        ("Introducción", "introduction"), ("Objetivos", "objectives"), ("Metodología general", "methodology"),
    ))
    closing = "".join(text_block(label, field) for label, field in (
        ("Discusión", "discussion"), ("Limitaciones", "limitations"), ("Conclusiones", "conclusions"), ("Fuentes adicionales", "sources"),
    ))
    saved = {entry["id"]: entry for entry in entries}
    included = []
    include_plotly = True
    for ref in draft["entries"]:
        if ref not in saved:
            continue
        entry = saved[ref]
        item = tables.get(entry["dataset"], {})
        provenance = {"tabla": item.get("title"), "versión": entry["dataset"], "fecha de ejecución": entry["created"],
                      "fuentes": item.get("sources", []), "metadatos": item.get("metadata", {}),
                      "operaciones": item.get("history", []), "configuración": entry["params"]}
        geometry_and_charts = []
        for figure in entry["figures"]:
            geometry_and_charts.append(figure.to_html(full_html=False, include_plotlyjs=include_plotly))
            include_plotly = False
        rendered = entry["table"].head(500).to_html(index=False, escape=True) if len(entry["table"].columns) else ""
        warnings = version_warnings(tables, entry["dataset"])
        if entry.get("snapshot") and entry["snapshot"] != item.get("snapshot"):
            warnings.append("El identificador de versión de la tabla no coincide con el resultado guardado.")
        note_items = "".join(f"<li>{paragraph(note)}</li>" for note in [*warnings, *entry["notes"]])
        limit = "<p>Vista de las primeras 500 filas. El CSV del cuaderno contiene la tabla completa.</p>" if len(entry["table"]) > 500 else ""
        annotation = (f"<p><strong>Anotación.</strong> {paragraph(entry['annotation'])}</p>"
                      if entry.get("annotation") else "")
        interpretation = (f"<p><strong>Interpretación del equipo.</strong> {paragraph(entry['interpretation'])}</p>"
                          if entry.get("interpretation") else "")
        metadata = escape(json.dumps(provenance, ensure_ascii=False, indent=2, default=str))
        included.append(f"""<article><h3>{paragraph(entry['title'])}</h3><p>{paragraph(entry['summary'])}</p>
{annotation}{interpretation}<ul>{note_items}</ul>{"".join(geometry_and_charts)}<div class="table">{rendered}</div>{limit}
<details><summary>Procedencia y parámetros</summary><pre>{metadata}</pre></details></article>""")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{font:16px system-ui,sans-serif;background:#0D1117;color:#edf3f9;margin:auto;max-width:76rem;padding:1.25rem}}
h1{{font-size:2.5rem;letter-spacing:-.04em}} article{{padding:1rem;border:1px solid #2b3946;border-radius:.65rem;margin-bottom:1.4rem}}
table{{border-collapse:collapse;text-align:left}}th,td{{border:1px solid #2b3946;padding:.4rem .65rem}}summary{{cursor:pointer}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.table{{overflow:auto}}p,li{{line-height:1.55}}
@media print{{body{{background:white;color:black}}thead{{display:table-header-group}}tr,.plotly-graph-div{{break-inside:avoid}}}}
</style></head><body><header><h1>{escape(title)}</h1><p>{paragraph(project.get('question', ''))}</p></header>
{introduction}<section><h2>Resultados</h2>{"".join(included)}</section>{closing}</body></html>"""
