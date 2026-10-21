"""Offline controller reference. Never reads or changes installed game bindings."""
from datetime import date
from html import escape
from pathlib import Path
import re
import tomllib
from urllib.parse import urlparse

GUIDES = Path(__file__).with_name("controls")
EVIDENCE = {"tested": "User tested", "default": "Mod default", "dependent": "Profile dependent"}


def load(recipe_id):
    if not isinstance(recipe_id, str) or not re.fullmatch(r"[a-z0-9-]+", recipe_id):
        raise ValueError("Invalid game ID")
    path = GUIDES / f"{recipe_id}.toml"
    if not path.is_file():
        return None
    with path.open("rb") as f:
        guide = tomllib.load(f)
    validate(guide, recipe_id)
    return guide


def validate(guide, recipe_id):
    def need(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{recipe_id}: missing controller reference text")
    if guide.get("id") != recipe_id:
        raise ValueError(f"{recipe_id}: mismatched controller reference")
    for key in ("title", "scope", "version", "reviewed"):
        need(guide.get(key))
    date.fromisoformat(guide["reviewed"])
    sources = guide.get("sources", {})
    if not isinstance(sources, dict) or not sources:
        raise ValueError(f"{recipe_id}: sources required")
    for source in sources.values():
        need(source.get("label"))
        need(source.get("detail"))
        url = source.get("url")
        if url and (urlparse(url).scheme != "https" or not urlparse(url).hostname):
            raise ValueError(f"{recipe_id}: unsafe source link")
    sections = guide.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError(f"{recipe_id}: control sections required")
    for section in sections:
        need(section.get("name"))
        if not section.get("bindings"):
            raise ValueError(f"{recipe_id}: empty control section")
        for row in section["bindings"]:
            for key in ("input", "action", "note"):
                need(row.get(key))
            if row.get("evidence") not in EVIDENCE or row.get("source") not in sources:
                raise ValueError(f"{recipe_id}: invalid control evidence/source")
            if row["evidence"] == "tested" and not sources[row["source"]].get("user_report"):
                raise ValueError(f"{recipe_id}: tested control requires a user report")
    for note in guide.get("notes", []):
        need(note)


def filtered_sections(guide, query="", category="All sections"):
    words = query.casefold().split()
    found = []
    for section in guide["sections"]:
        if category != "All sections" and category != section["name"]:
            continue
        rows = []
        for row in section["bindings"]:
            searchable = " ".join([section["name"], row["input"], row["action"], row["note"],
                                   EVIDENCE[row["evidence"]]]).casefold()
            if all(word in searchable for word in words):
                rows.append(row)
        if rows:
            found.append({"name": section["name"], "bindings": rows})
    return found


def html(guide, query="", category="All sections"):
    e = escape
    parts = [f'<h2>{e(guide["title"])}</h2>', f'<p>{e(guide["scope"])}</p>',
             f'<p style="color:#A7ADB7">{e(guide["version"])} · Reviewed {e(guide["reviewed"])}</p>',
             '<p><b>Evidence:</b> User tested = reported on this setup; Mod default = documented mapping; '
             'Profile dependent = review the selected preset. Current bindings are not scanned.</p>']
    sections = filtered_sections(guide, query, category)
    if not sections:
        parts.append('<p><b>No matching controls.</b> Clear the search or choose another section.</p>')
    for section in sections:
        parts.append(f'<h3 style="color:#FFD21A">{e(section["name"])}</h3><table width="100%" cellspacing="0" cellpadding="7" border="0">'
                     '<tr bgcolor="#14212B"><th align="left">Input</th><th align="left">Action / context</th><th align="left">Evidence</th></tr>')
        for i, row in enumerate(section["bindings"]):
            colour = "#11161B" if i % 2 else "#171D23"
            source = guide["sources"][row["source"]]
            label = EVIDENCE[row["evidence"]]
            if source.get("url"):
                label = f'<a style="color:#23B7FF" href="{e(source["url"], quote=True)}">{e(label)}</a>'
            else:
                label = e(label)
            parts.append(f'<tr bgcolor="{colour}"><td width="27%"><b>{e(row["input"])}</b></td>'
                         f'<td width="53%">{e(row["action"])}<br><span style="color:#A7ADB7">{e(row["note"])}</span></td>'
                         f'<td width="20%">{label}<br><small>{e(source["label"])}</small></td></tr>')
        parts.append('</table>')
    parts.append('<h3>Notes and limitations</h3><ul>')
    parts.extend(f'<li>{e(note)}</li>' for note in guide.get("notes", []))
    parts.append('</ul><h3>Sources</h3>')
    for source in guide["sources"].values():
        label = e(source["label"])
        if source.get("url"):
            label = f'<a style="color:#23B7FF" href="{e(source["url"], quote=True)}">{label}</a>'
        parts.append(f'<p><b>{label}</b> — {e(source["detail"])}</p>')
    return "".join(parts)


def plain_text(guide):
    parts = [guide["title"], guide["scope"], f'{guide["version"]}; reviewed {guide["reviewed"]}',
             'Reference only; current bindings are not scanned. L3/R3 mean thumbstick clicks.', '']
    for section in guide["sections"]:
        parts.append(section["name"])
        for row in section["bindings"]:
            source = guide["sources"][row["source"]]
            parts.append(f'  {row["input"]}: {row["action"]} [{EVIDENCE[row["evidence"]]}; {source["label"]}]')
            parts.append(f'    {row["note"]}')
        parts.append('')
    parts += ['Notes and limitations', *guide.get('notes', []), '', 'Sources']
    for source in guide["sources"].values():
        parts.append(f'{source["label"]}: {source["detail"]}' + (f' {source["url"]}' if source.get('url') else ''))
    return '\n'.join(parts)
