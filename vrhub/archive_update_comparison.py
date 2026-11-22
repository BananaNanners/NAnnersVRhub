# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only installed/downloaded/online evidence comparison.

Never turns release labels, Hub install timestamps or a downloaded file into
installation authority. No network, filesystem writes, or installer actions.
"""
from pathlib import Path
from . import download_planner as planner, updates, installed_provenance


def _online_item(recipe, comp, online):
    """Only explicit Nexus IDs or a unique typed GitHub recipe target may match."""
    if not isinstance(online, list):
        return None
    online = [item for item in online if isinstance(item, dict)]
    rid = str(comp["id"])
    if rid.isdecimal():
        hits = [x for x in online if str(x.get("mod_id", "")) == rid]
        return hits[0] if len(hits) == 1 else None
    source = recipe.get("archive_releases", {}).get(rid, {})
    repo = source.get("repo")
    if not repo:
        return None
    kind = ("Profile" if rid == "profile" else "Mod")
    targets = [u for u in recipe.get("updates", [])
               if u.get("github") == repo and u.get("dependency_type", "Mod") == kind]
    if len(targets) != 1:
        return None
    hits = [x for x in online if x.get("name") == targets[0].get("name")]
    return hits[0] if len(hits) == 1 else None


def _download(recipe, comp, row, warning):
    """Only pinned hashes and matching official digest tags identify a release."""
    if row is None:
        return "Not scanned", None, False, "No active scan for this dependency.", "unknown"
    status = row.get("status", "Not checked")
    if warning:
        return "Scan incomplete", None, False, str(warning), "warning"
    if status in ("Archive changed — rescan required", "Not checked"):
        return "Rescan needed", None, False, "Historical archive identity is not fresh.", "warning"
    if not row.get("file"):
        return "Not found", None, False, "No matching archive found in active scan folders.", "unknown"
    if status == "Hash not verified — do not install":
        return "Unverified hash", None, False, "Archive cannot pass pinned verification.", "danger"
    candidates = row.get("candidates", [])
    selected = candidates[0] if candidates and candidates[0].get("file") == row.get("file") else None
    if row.get("candidate_incomplete") or row.get("ambiguous"):
        return "Choose archive", None, False, "Multiple or incomplete candidate identities.", "warning"
    source = recipe.get("archive_releases", {}).get(str(comp["id"]), {})
    if status == "Pinned SHA-256 verified":
        tag = source.get("pinned_tag")
        value = "Pinned SHA-256" + (f" · {tag}" if tag else "")
        return value, str(tag) if tag else None, True, (
            "Downloaded bytes match this recipe's SHA-256; installed version is independent."), "success"
    if row.get("release_review"):
        if not selected or not selected.get("sha256") or not selected.get("tags"):
            return "Hash mismatch · blocked", None, False, "Official identity incomplete.", "danger"
        tag = str(row.get("release_expected") or selected["tags"][0])
        return "Official " + tag + " · pin blocked", tag, True, (
            "Upstream digest matched but differs from recipe pin; installation blocked."), "warning"
    if status in ("Hash mismatch — do not install",):
        return "Hash mismatch · blocked", None, False, "Recipe-pinned hash did not match.", "danger"
    if selected and selected.get("sha256") and selected.get("tags"):
        tag = str(row.get("release_expected") if selected.get("expected") else selected["tags"][0])
        return "Official " + tag + " · review", tag, True, (
            "Official release SHA-256 matched; this does not establish installed compatibility."), "warning"
    if status == "Possible archive — inspect first":
        if str(comp["id"]).isdecimal():
            hint = updates._installed_archive_version(Path(row["file"]).name, int(comp["id"]))
            if hint:
                return "Filename suggests " + ".".join(map(str, hint)), None, False, (
                    "Filename only, not a verified release or an approved update."), "warning"
        return "Unverified archive", None, False, "Filename match only; release unknown.", "warning"
    return "Review required", None, False, "No verified release identity.", "warning"


def compare(recipe, plan, state, online=None):
    """Return presentation records only; no installation decisions or mutations."""
    if not recipe:
        return []
    components = planner.plan_components(recipe)
    rows = plan.get("rows", []) if isinstance(plan, dict) else []
    by_id = {str(r["id"]): r for r in rows if isinstance(r, dict) and "id" in r}
    warning = plan.get("warning") if isinstance(plan, dict) else None
    out = []
    for comp in components:
        if comp["id"] == "guide":
            continue
        update = _online_item(recipe, comp, online)
        provenance = installed_provenance.evidence(
            recipe, comp, state, by_id.get(comp["id"]), warning)
        installed = provenance["label"]
        recorded_version = provenance["version"]
        installed_note = provenance["detail"]
        downloaded, download_tag, verified, download_note, tone = _download(
            recipe, comp, by_id.get(comp["id"]), warning)
        if update and update.get("latest_version"):
            latest = str(update["latest_version"])
            latest_note = "Last online update check; not a live scan or compatibility approval."
        elif update and update.get("status") in ("error", "no_key"):
            latest = "Unavailable"
            latest_note = "Update check failed or Nexus key unavailable."
        else:
            latest = "Not checked"
            latest_note = "Use Refresh update status in Updates; no network request made here."
        if tone == "danger":
            assessment = "Verification blocked"
        elif warning or downloaded in ("Not scanned", "Rescan needed", "Scan incomplete"):
            assessment = "Scan / rescan needed"
        elif downloaded == "Not found":
            assessment = "Download missing"
        elif downloaded == "Choose archive":
            assessment = "Manual archive choice"
        elif str(comp["id"]) == "guide":
            assessment = "Follow setup guide"
        elif (not verified and recorded_version and str(comp["id"]).isdecimal()
              and downloaded.startswith("Filename suggests ")
              and by_id.get(comp["id"], {}).get("status") == "Possible archive — inspect first"):
            hint = updates._installed_archive_version(
                Path(by_id[comp["id"]]["file"]).name, int(comp["id"]))
            old = updates._release_version(recorded_version)
            if hint and old:
                order = updates._ordered_numeric(old, hint)
                assessment = (
                    "Filename suggests newer · verify ZIP" if order < 0 else
                    "Filename suggests older · verify ZIP" if order > 0 else
                    "Filename label matches record · verify bytes")
            else:
                assessment = "Filename hint · archive unverified"
        elif not verified:
            assessment = "Archive needs review"
        elif "pin blocked" in downloaded:
            assessment = "New release · recipe pin blocked"
        elif recorded_version and download_tag:
            old, new = updates._release_version(recorded_version), updates._release_version(download_tag)
            order = updates._ordered_numeric(old, new) if old and new else None
            if order is not None and order < 0:
                assessment = "Downloaded newer than recorded · review"
            elif order is not None and order > 0:
                assessment = "Downloaded older than recorded · review"
            elif order == 0 or recorded_version == download_tag:
                assessment = "Release labels match · verify installed files"
            else:
                assessment = "Different release labels · review"
        elif verified:
            assessment = "Downloaded identity verified · install unknown"
        else:
            assessment = "Review required"
        if verified and download_tag and latest not in ("Not checked", "Unavailable"):
            a, b = updates._release_version(download_tag), updates._release_version(latest)
            if a and b and updates._ordered_numeric(a, b) < 0:
                assessment += " · newer upstream"
            elif download_tag == latest:
                assessment += " · latest label matches"
        out.append({
            "id": str(comp["id"]), "name": str(comp["name"]),
            "installed": installed, "downloaded": downloaded, "latest": latest,
            "assessment": assessment, "tone": tone,
            "provenance_source": provenance["source"],
            "installed_attributed": provenance["identified"],
            "detail": chr(10).join((
                "Installed evidence: " + provenance["source"],
                "Installed: " + installed_note,
                "Downloaded: " + download_note,
                "Latest online: " + latest_note,
                "Version labels do not authorize installation or replacement.")),
            "matched_release": bool(verified),
        })
    return out
