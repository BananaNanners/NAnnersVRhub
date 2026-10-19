"""Read-only, dated compatibility references and current local evidence.

Compatibility metadata is deliberately separate from installable UEVR profiles.
A historical gameplay result never certifies the current machine or game session.
"""
from datetime import date, datetime, timezone
import html
from pathlib import Path

from . import __version__, runtime
from .display_time import local_time
from .schema import RecipeError

FIELDS = (("runtime", "OpenXR runtime"), ("proton", "Proton policy"),
          ("adapter", "OpenVR adapter"), ("launch", "Launch route"))
REFERENCE_FIELDS = (("tested_on", "Test date"), ("source", "Evidence source"),
                    ("system", "System"), ("headset", "Headset"),
                    ("modlist", "Modlist"), ("proton", "Proton"), ("result", "Result"))
LIMITATION = ("Local configuration checks do not verify current rendering, controller input or gameplay. "
              "A dated reference, when present, records a user-reported test on one setup. "
              "Headset connection remains available in VR System; controllers require a live game test.")


def validate(value, source="recipe"):
    if not isinstance(value, dict):
        raise RecipeError(f"{source}: compatibility must be a table")
    allowed = {key for key, _ in FIELDS} | {"requirements", "notes", "reference", "validation", "checks", "manual_checks", "workarounds"}
    if set(value) - allowed:
        raise RecipeError(f"{source}: unknown compatibility field(s): {', '.join(sorted(set(value)-allowed))}")
    for key, _ in FIELDS:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise RecipeError(f"{source}: compatibility.{key} must be a non-empty string")
    if value["runtime"] not in {"WiVRn", "Monado", "SteamVR", "any"}:
        raise RecipeError(f"{source}: unsupported compatibility.runtime")
    for key in ("requirements", "notes", "manual_checks", "workarounds"):
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            raise RecipeError(f"{source}: compatibility.{key} must be a list of non-empty strings")
    evidence = value.get("validation", "unverified")
    if not isinstance(evidence, str) or evidence not in {"unverified", "experimental", "user-reported", "user-reported-workaround"}:
        raise RecipeError(f"{source}: invalid compatibility.validation")
    if evidence in {"user-reported", "user-reported-workaround"} and not value.get("reference"):
        raise RecipeError(f"{source}: user-reported validation needs a dated reference")
    if evidence == "user-reported-workaround" and not value.get("workarounds"):
        raise RecipeError(f"{source}: user-reported-workaround validation needs documented workarounds")
    if "checks" in value:
        from .compatibility_checks import validate as validate_checks
        validate_checks(value["checks"], source)
    ref = value.get("reference")
    if ref is not None:
        if not isinstance(ref, dict) or set(ref) != {k for k, _ in REFERENCE_FIELDS}:
            raise RecipeError(f"{source}: compatibility.reference needs all reference fields and no unknown fields")
        for key, _ in REFERENCE_FIELDS:
            if not isinstance(ref[key], str) or not ref[key].strip():
                raise RecipeError(f"{source}: compatibility.reference.{key} must be a non-empty string")
        try:
            date.fromisoformat(ref["tested_on"])
        except ValueError as exc:
            raise RecipeError(f"{source}: compatibility.reference.tested_on must be an ISO date") from exc


def evidence_text(profile):
    return {"user-reported-workaround": "USER-REPORTED LIVE TEST — WORKAROUND REQUIRED (experimental)",
            "user-reported": "USER-REPORTED LIVE TEST (dated reference; not a current session)",
            "experimental": "EXPERIMENTAL — live VR gameplay unverified in this profile",
            "unverified": "UNVERIFIED — no dated live gameplay reference recorded"}[profile.get("validation", "unverified")]


def summary_text(recipe):
    profile = recipe.get("compatibility")
    if profile is None:
        return "Compatibility profile: NOT YET DOCUMENTED. Use the existing setup guide and Preflight."
    lines = ["Compatibility profile", "Gameplay evidence: " + evidence_text(profile)]
    if profile.get("workarounds"):
        lines += ["Required workaround (recorded test conditions):", *[f"  - {x}" for x in profile["workarounds"]]]
    lines += [f"{label}: {profile[key]}" for key, label in FIELDS]
    for key, title in (("requirements", "Launch requirements"), ("notes", "Notes")):
        if profile.get(key):
            lines += [title + ":", *[f"  - {x}" for x in profile[key]]]
    if profile.get("reference"):
        lines += ["Dated gameplay reference (user reported; not a current test)"]
        lines += [f"{label}: {profile['reference'][key]}" for key, label in REFERENCE_FIELDS]
    else:
        lines.append("Dated gameplay reference: none recorded")
    return "\n".join(lines)


def report(recipe, steam_roots=None):
    # Lazy import avoids a hub/schema dependency cycle.
    from . import hub
    from .handlers import get_handler
    profile = recipe.get("compatibility")
    out = {"schema_version": 1, "hub_version": __version__, "recipe_id": recipe["id"],
           "game": recipe["name"], "sampled_at": datetime.now(timezone.utc).isoformat(),
           "profile": profile, "limitation": LIMITATION, "checks": [], "status": "NOT DOCUMENTED"}
    from . import live_tests
    try:
        local_history = live_tests.history(recipe["id"])
        out["local_test"] = local_history[0] if local_history else None
        out["local_test_count"] = len(local_history)
        out["local_test_error"] = ""
    except RuntimeError as exc:
        out["local_test"] = None
        out["local_test_count"] = None
        out["local_test_error"] = str(exc)
    if profile is None:
        return out
    preflight = hub.preflight(recipe, steam_roots)
    for row in preflight["rows"]:
        out["checks"].append({"name": row["name"], "status": "ok" if row["ok"] else
                              ("error" if row.get("required", True) else "warning"), "detail": row["detail"]})
    path, lib = runtime.active_runtime()
    selected = runtime.runtime_name(path, lib)
    expected = profile["runtime"]
    matches = bool(lib) and (expected == "any" or expected == selected)
    out["checks"].append({"name": "Profile runtime", "status": "ok" if matches else "error",
                          "detail": f"Expected: {expected}; selected: {selected}; manifest: {path or 'not found'}"})
    if lib and path:
        library = Path(lib)
        if library.is_absolute() or "/" in lib:
            try:
                library = (library if library.is_absolute() else path.resolve().parent / library).resolve()
                present = library.is_file()
            except (OSError, RuntimeError):
                present = False
            out["checks"].append({"name": "Runtime library file", "status": "ok" if present else "error",
                                  "detail": f"{library}: " + ("present; not loaded" if present else "missing or inaccessible")})
        else:
            out["checks"].append({"name": "Runtime library file", "status": "unknown",
                                  "detail": f"{lib}: dynamic linker lookup; loading is unverified."})
    from .compatibility_checks import rows as workflow_rows
    out["checks"].extend(workflow_rows(recipe, hub.game_path(recipe, steam_roots)))
    out["checks"].extend(get_handler(recipe).compatibility_rows(recipe, hub.game_path(recipe, steam_roots)))
    statuses = {row["status"] for row in out["checks"]}
    out["status"] = ("NOT READY" if "error" in statuses else "INCOMPLETE" if "unknown" in statuses else
                     "REVIEW REQUIRED" if "warning" in statuses else "LOCAL CHECKS PASSED")
    return out


def local_test_text(report):
    from . import live_tests
    if report.get("local_test_error"):
        return "Local gameplay history unavailable: " + report["local_test_error"]
    if report.get("local_test"):
        return live_tests.record_text(report["local_test"]) + f"\nLocal test records: {report['local_test_count']} (see Test history for earlier entries)."
    return "Local gameplay test: NOT RECORDED. Bundled references below are separate from your local history."


def report_text(report):
    recipe = {"compatibility": report["profile"]} if report["profile"] is not None else {}
    lines = [f"NAnnersVRhub {report['hub_version']} — Compatibility report", report["game"],
             f"Recipe: {report['recipe_id']}", f"Sampled: {local_time(report['sampled_at'])}", "Local configuration: " + report["status"],
             "", local_test_text(report), "", "Bundled compatibility reference:",
             summary_text(recipe), "", "Current local evidence:"]
    lines += [f"[{row['status'].upper()}] {row['name']}: {row['detail']}" for row in report["checks"]]
    if not report["checks"]:
        lines.append("No profile-specific evaluation; the game still has its existing Preflight and guide.")
    lines += ["", report["limitation"]]
    return "\n".join(lines)


def report_html(report):
    e = html.escape
    colours = {"ok": "#4FE39A", "error": "#FF5B50", "warning": "#FFD21A", "unknown": "#A5B2C2"}
    colour = "#4FE39A" if report["status"] == "LOCAL CHECKS PASSED" else "#FF5B50" if report["status"] == "NOT READY" else "#FFD21A"
    out = ['<style>body{color:#F5F2DE;}h2,h3{color:#FFD21A;}td{padding:5px;}</style>',
           f"<h2>{e(report['game'])}</h2>",
           f"<p><b style='color:{colour}'>Local configuration: {e(report['status'])}</b><br>Sampled: {e(local_time(report['sampled_at']))}</p>"]
    out.append("<h3>Latest local gameplay test</h3><p>" + e(local_test_text(report)).replace("\n", "<br>") + "</p>")
    profile = report["profile"]
    out.append("<h3>Bundled compatibility reference</h3>")
    if profile is None:
        out.append("<p>Compatibility profile: <b>NOT YET DOCUMENTED</b>. Use the existing setup guide and Preflight.</p>")
    else:
        out.append(f"<p><b>Gameplay evidence:</b> {e(evidence_text(profile))}</p>")
        if profile.get("workarounds"):
            out.append("<h3>Required workaround</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in profile["workarounds"]) + "</ul>")
        out.append("<h3>Expected configuration</h3><table>")
        out += [f"<tr><td><b>{label}</b></td><td>{e(profile[key])}</td></tr>" for key, label in FIELDS]
        out.append("</table><h3>Current local evidence</h3><table>")
        for row in report["checks"]:
            out.append(f"<tr><td style='color:{colours[row['status']]}'><b>{row['status'].upper()}</b></td>"
                       f"<td><b>{e(row['name'])}</b><br>{e(row['detail'])}</td></tr>")
        out.append("</table>")
        for key, title in (("requirements", "Launch requirements"), ("notes", "Notes")):
            if profile.get(key):
                out.append(f"<h3>{title}</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in profile[key]) + "</ul>")
        ref = profile.get("reference")
        out.append("<h3>Dated gameplay reference</h3><p>User reported; not a current test.</p>")
        if ref:
            out.append("<table>" + "".join(f"<tr><td><b>{label}</b></td><td>{e(ref[key])}</td></tr>"
                                         for key, label in REFERENCE_FIELDS) + "</table>")
        else:
            out.append("<p>No dated gameplay reference recorded.</p>")
    out.append(f"<p>{e(report['limitation'])}</p>")
    return "".join(out)
